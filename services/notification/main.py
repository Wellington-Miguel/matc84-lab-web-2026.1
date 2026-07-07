import os
import json
import uuid
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

import asyncpg
import boto3
from fastapi import FastAPI, Request, Response, HTTPException, status, TarefasBackground
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, Gauge, generate_latest
from pydantic import BaseModel, field_validator, EmailStr
import aiofiles

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

from shared.logger import get_logger, LogContext, Timer

logger = get_logger("notification-service")

# Métricas
REQUISICOES_TOTAL = Counter("http_requests_total", "Requisições HTTP", ["metodo", "caminho", "status"])
DURACAO_REQUISICOES = Histogram("http_request_duration_seconds", "Duração requisição", ["metodo", "caminho"])
NOTIFICACOES_ENVIADAS = Counter("notifications_sent_total", "Notificações enviadas", ["tipo", "canal", "status"])
NOTIFICACOES_ENFILEIRADAS = Gauge("notifications_queued", "Notificações enfileiradas")
EVENTOS_SQS = Counter("sqs_events_processed_total", "Eventos SQS processados", ["tipo_evento", "status"])

# Configuração
URL_BD = os.getenv("DATABASE_URL", "postgresql://bebidasadmin:[REDACTED]@localhost/bebidas")
URL_FILA_SQS = os.getenv("SQS_NOTIFICATION_QUEUE_URL", "http://localstack:4566/000000000000/notifications.fifo")
REGIAO_AWS = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
AMBIENTE = os.getenv("ENVIRONMENT", "desenvolvimento")
EMAIL_DE = os.getenv("EMAIL_FROM", "noreply@bebidas.local")
SMS_DE = os.getenv("SMS_FROM", "+55 11 9999-9999")

# Globais
pool_bd: asyncpg.Pool = None
cliente_sqs = None
tarefa_consumidor = None


@asynccontextmanager
async def ciclo_vida(app: FastAPI):
    global pool_bd, cliente_sqs, tarefa_consumidor
    logger.info("notification-service.iniciando", extra={"ambiente": AMBIENTE})
    
    pool_bd = await asyncpg.create_pool(URL_BD, min_size=5, max_size=20)
    cliente_sqs = boto3.client("sqs", region_name=REGIAO_AWS)
    tarefa_consumidor = asyncio.create_task(_loop_consumidor_sqs())
    
    logger.info("notification-service.pronto")
    yield
    
    if tarefa_consumidor:
        tarefa_consumidor.cancel()
    await pool_bd.close()
    logger.info("notification-service.encerrando")


app = FastAPI(title="Notification Service", lifespan=ciclo_vida)


@app.middleware("http")
async def middleware_correlacao(requisicao: Request, proximo):
    id_correlacao = requisicao.headers.get("x-correlation-id") or str(uuid.uuid4())
    id_requisicao = str(uuid.uuid4())
    cronometro = Timer()
    codigo_status = 500

    with LogContext(correlation_id=id_correlacao, request_id=id_requisicao):
        try:
            resposta = await proximo(requisicao)
            codigo_status = resposta.status_code
            resposta.headers["x-correlation-id"] = id_correlacao
            return resposta
        finally:
            caminho = _obter_template_rota(requisicao)
            if caminho != "/metrics":
                REQUISICOES_TOTAL.labels(metodo=requisicao.method, caminho=caminho, status=str(codigo_status)).inc()
                DURACAO_REQUISICOES.labels(metodo=requisicao.method, caminho=caminho).observe(cronometro.elapsed_ms / 1000)


# Modelos
class RequisicaoEnviarNotificacao(BaseModel):
    id_destinatario: str
    tipo_notificacao: str
    titulo: str
    mensagem: str
    canais: list[str] = ["email"]

    @field_validator("canais")
    @classmethod
    def validar_canais(cls, v):
        validos = {"email", "sms", "push"}
        if not all(c in validos for c in v):
            raise ValueError(f"Canais válidos: {validos}")
        return v


class RequisicaoPreferenciaNotificacao(BaseModel):
    id_destinatario: str
    email: Optional[EmailStr] = None
    telefone: Optional[str] = None
    token_push: Optional[str] = None
    preferencias: dict = {}

    @field_validator("telefone")
    @classmethod
    def validar_telefone(cls, v):
        if v and not v.startswith("+"):
            raise ValueError("Telefone deve começar com +")
        return v


# Endpoints
@app.get("/health")
async def verificacao_saude():
    verificacoes = {}
    try:
        await pool_bd.fetchval("SELECT 1")
        verificacoes["bd"] = "ok"
    except Exception as e:
        verificacoes["bd"] = f"erro: {str(e)}"

    try:
        resposta = cliente_sqs.get_queue_attributes(QueueUrl=URL_FILA_SQS, AttributeNames=["ApproximateNumberOfMessages"])
        verificacoes["sqs"] = "ok"
        verificacoes["mensagens_enfileiradas"] = int(resposta["Attributes"]["ApproximateNumberOfMessages"])
    except Exception as e:
        verificacoes["sqs"] = f"erro: {str(e)}"

    tudo_ok = all(v == "ok" for v in verificacoes.values() if isinstance(v, str))
    return JSONResponse(
        status_code=200 if tudo_ok else 503,
        content={"status": "saudavel" if tudo_ok else "degradado", "verificacoes": verificacoes}
    )


@app.get("/metrics")
async def metricas():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/notificacoes/enviar", status_code=202)
async def enviar_notificacao(requisicao: RequisicaoEnviarNotificacao, tarefas: TarefasBackground):
    cronometro = Timer()
    id_notificacao = str(uuid.uuid4())

    await pool_bd.execute(
        "INSERT INTO notifications (id, recipient_id, notification_type, title, message, channels, status, created_at) VALUES ($1, $2, $3, $4, $5, $6, 'pending', NOW())",
        id_notificacao, requisicao.id_destinatario, requisicao.tipo_notificacao, requisicao.titulo, requisicao.mensagem, json.dumps(requisicao.canais),
    )

    tarefas.add_task(_tarefa_enviar_notificacao, id_notificacao, requisicao.id_destinatario, requisicao.canais, requisicao.titulo, requisicao.mensagem)

    logger.info("notificacao.enfileirada", extra={"id_notificacao": id_notificacao, "tempo_ms": cronometro.elapsed_ms})
    NOTIFICACOES_ENVIADAS.labels(tipo=requisicao.tipo_notificacao, canal="enfileirada", status="pendente").inc()

    return {"id_notificacao": id_notificacao, "status": "pendente", "mensagem": "Notificação enfileirada para envio"}


@app.get("/notificacoes/{id_notificacao}")
async def obter_status_notificacao(id_notificacao: str):
    linha = await pool_bd.fetchrow(
        "SELECT id, notification_type, status, channels, created_at, sent_at FROM notifications WHERE id = $1",
        id_notificacao
    )

    if not linha:
        raise HTTPException(status_code=404, detail="Notificação não encontrada")

    return {
        "id": linha["id"],
        "tipo_notificacao": linha["notification_type"],
        "status": linha["status"],
        "canais": json.loads(linha["channels"]),
        "data_criacao": linha["created_at"].isoformat(),
        "data_envio": linha["sent_at"].isoformat() if linha["sent_at"] else None,
    }


@app.post("/preferencias", status_code=201)
async def configurar_preferencias(requisicao: RequisicaoPreferenciaNotificacao):
    cronometro = Timer()

    await pool_bd.execute(
        "INSERT INTO notification_preferences (recipient_id, email, phone, push_token, preferences, updated_at) VALUES ($1, $2, $3, $4, $5, NOW()) ON CONFLICT (recipient_id) DO UPDATE SET email = EXCLUDED.email, phone = EXCLUDED.phone, push_token = EXCLUDED.push_token, preferences = EXCLUDED.preferences, updated_at = NOW()",
        requisicao.id_destinatario, requisicao.email, requisicao.telefone, requisicao.token_push, json.dumps(requisicao.preferencias),
    )

    logger.info("notificacao.preferencias_atualizadas", extra={"id_destinatario": requisicao.id_destinatario, "tempo_ms": cronometro.elapsed_ms})
    return {"id_destinatario": requisicao.id_destinatario, "mensagem": "Preferências atualizadas com sucesso"}


@app.get("/preferencias/{id_destinatario}")
async def obter_preferencias(id_destinatario: str):
    linha = await pool_bd.fetchrow("SELECT recipient_id, email, phone, push_token, preferences FROM notification_preferences WHERE recipient_id = $1", id_destinatario)

    if not linha:
        return {"id_destinatario": id_destinatario, "email": None, "telefone": None, "token_push": None, "preferencias": {}, "mensagem": "Sem preferências configuradas"}

    return {
        "id_destinatario": linha["recipient_id"],
        "email": linha["email"],
        "telefone": linha["phone"],
        "token_push": linha["push_token"],
        "preferencias": json.loads(linha["preferences"]) if linha["preferences"] else {},
    }


async def _loop_consumidor_sqs():
    logger.info("sqs_consumidor.iniciado")

    while True:
        try:
            resposta = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: cliente_sqs.receive_message(QueueUrl=URL_FILA_SQS, MaxNumberOfMessages=10, WaitTimeSeconds=20)
            )

            mensagens = resposta.get("Messages", [])
            if not mensagens:
                continue

            for msg in mensagens:
                try:
                    corpo = json.loads(msg["Body"])
                    tipo_evento = corpo.get("eventType", "desconhecido")

                    if tipo_evento == "pedido.criado":
                        await _manipular_pedido_criado(corpo)
                    elif tipo_evento == "pagamento.concluido":
                        await _manipular_pagamento_concluido(corpo)
                    elif tipo_evento == "pagamento.falhou":
                        await _manipular_pagamento_falhou(corpo)
                    elif tipo_evento == "estoque.baixo":
                        await _manipular_estoque_baixo(corpo)
                    else:
                        EVENTOS_SQS.labels(tipo_evento=tipo_evento, status="desconhecido").inc()

                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: cliente_sqs.delete_message(QueueUrl=URL_FILA_SQS, ReceiptHandle=msg["ReceiptHandle"])
                    )

                    EVENTOS_SQS.labels(tipo_evento=tipo_evento, status="sucesso").inc()

                except Exception as e:
                    logger.error("sqs_consumidor.erro_mensagem", extra={"erro": str(e)})
                    EVENTOS_SQS.labels(tipo_evento="desconhecido", status="erro").inc()

        except Exception as e:
            logger.error("sqs_consumidor.erro", extra={"erro": str(e)})
            await asyncio.sleep(5)


async def _manipular_pedido_criado(evento: dict):
    id_pedido = evento.get("pedidoId")
    id_cliente = evento.get("clienteId")
    total = evento.get("total")
    id_notificacao = str(uuid.uuid4())

    await pool_bd.execute(
        "INSERT INTO notifications (id, recipient_id, notification_type, title, message, channels, status, created_at) VALUES ($1, $2, $3, $4, $5, $6, 'pending', NOW())",
        id_notificacao, id_cliente, "pedido.criado", "Pedido confirmado!", f"Seu pedido {id_pedido} foi confirmado. Total: R$ {total:.2f}", json.dumps(["email", "push"]),
    )

    await _tarefa_enviar_notificacao(id_notificacao, id_cliente, ["email", "push"], "Pedido confirmado!", f"Seu pedido {id_pedido} foi confirmado. Total: R$ {total:.2f}")
    logger.info("notificacao.pedido_criado", extra={"id_pedido": id_pedido})


async def _manipular_pagamento_concluido(evento: dict):
    id_pedido = evento.get("pedidoId")
    id_cliente = evento.get("clienteId")
    id_notificacao = str(uuid.uuid4())

    await pool_bd.execute(
        "INSERT INTO notifications (id, recipient_id, notification_type, title, message, channels, status, created_at) VALUES ($1, $2, $3, $4, $5, $6, 'pending', NOW())",
        id_notificacao, id_cliente, "pagamento.concluido", "Pagamento aprovado!", f"Pagamento do pedido {id_pedido} foi aprovado. Seu pedido será entregue em breve.", json.dumps(["email", "sms", "push"]),
    )

    await _tarefa_enviar_notificacao(id_notificacao, id_cliente, ["email", "sms", "push"], "Pagamento aprovado!", f"Pagamento do pedido {id_pedido} foi aprovado. Seu pedido será entregue em breve.")
    logger.info("notificacao.pagamento_concluido", extra={"id_pedido": id_pedido})


async def _manipular_pagamento_falhou(evento: dict):
    id_pedido = evento.get("pedidoId")
    id_cliente = evento.get("clienteId")
    motivo = evento.get("motivo", "Motivo desconhecido")
    id_notificacao = str(uuid.uuid4())

    await pool_bd.execute(
        "INSERT INTO notifications (id, recipient_id, notification_type, title, message, channels, status, created_at) VALUES ($1, $2, $3, $4, $5, $6, 'pending', NOW())",
        id_notificacao, id_cliente, "pagamento.falhou", "Falha no pagamento", f"Não conseguimos processar seu pagamento. Motivo: {motivo}. Por favor, tente novamente.", json.dumps(["email", "sms"]),
    )

    await _tarefa_enviar_notificacao(id_notificacao, id_cliente, ["email", "sms"], "Falha no pagamento", f"Não conseguimos processar seu pagamento. Motivo: {motivo}. Por favor, tente novamente.")
    logger.info("notificacao.pagamento_falhou", extra={"id_pedido": id_pedido})


async def _manipular_estoque_baixo(evento: dict):
    id_sku = evento.get("skuId")
    quantidade_atual = evento.get("quantidadeAtual")
    limite = evento.get("limite", 50)
    id_notificacao = str(uuid.uuid4())
    id_admin = "admin@bebidas.local"

    await pool_bd.execute(
        "INSERT INTO notifications (id, recipient_id, notification_type, title, message, channels, status, created_at) VALUES ($1, $2, $3, $4, $5, $6, 'pending', NOW())",
        id_notificacao, id_admin, "estoque.baixo", "⚠️ Estoque Baixo", f"SKU {id_sku} está com apenas {quantidade_atual} unidades (limite: {limite}). Reposição urgente!", json.dumps(["email"]),
    )

    await _tarefa_enviar_notificacao(id_notificacao, id_admin, ["email"], "⚠️ Estoque Baixo", f"SKU {id_sku} está com apenas {quantidade_atual} unidades (limite: {limite}). Reposição urgente!")
    logger.warning("notificacao.estoque_baixo", extra={"id_sku": id_sku})


async def _tarefa_enviar_notificacao(id_notificacao: str, id_destinatario: str, canais: list[str], titulo: str, mensagem: str):
    cronometro = Timer()

    prefs_linha = await pool_bd.fetchrow("SELECT email, phone, push_token FROM notification_preferences WHERE recipient_id = $1", id_destinatario)

    resultados = {}

    for canal in canais:
        try:
            if canal == "email" and prefs_linha and prefs_linha["email"]:
                resultados["email"] = await _enviar_email(prefs_linha["email"], titulo, mensagem, id_notificacao)
            elif canal == "sms" and prefs_linha and prefs_linha["phone"]:
                resultados["sms"] = await _enviar_sms(prefs_linha["phone"], mensagem, id_notificacao)
            elif canal == "push" and prefs_linha and prefs_linha["push_token"]:
                resultados["push"] = await _enviar_push(prefs_linha["push_token"], titulo, mensagem, id_notificacao)
        except Exception as e:
            logger.error(f"notificacao.{canal}_falhou", extra={"id_notificacao": id_notificacao, "erro": str(e)})
            resultados[canal] = False

    sucesso = any(resultados.values())
    status = "enviada" if sucesso else "falhou"

    await pool_bd.execute("UPDATE notifications SET status = $1, sent_at = NOW() WHERE id = $2", status, id_notificacao)

    logger.info("notificacao.enviada", extra={"id_notificacao": id_notificacao, "tempo_ms": cronometro.elapsed_ms})

    for canal, flag_sucesso in resultados.items():
        NOTIFICACOES_ENVIADAS.labels(tipo="notificacao", canal=canal, status="sucesso" if flag_sucesso else "falhou").inc()


async def _enviar_email(email: str, titulo: str, mensagem: str, id_notificacao: str) -> bool:
    if AMBIENTE == "producao":
        pass
    else:
        caminho_arquivo = f"/tmp/notifications/email_{id_notificacao}.txt"
        try:
            os.makedirs("/tmp/notifications", exist_ok=True)
            async with aiofiles.open(caminho_arquivo, "w") as f:
                await f.write(f"Para: {email}\nAssunto: {titulo}\n\n{mensagem}\n")
            logger.info(f"Email simulado enviado para {email}")
            return True
        except Exception as e:
            logger.error(f"Email simulado falhou: {e}")
            return False


async def _enviar_sms(telefone: str, mensagem: str, id_notificacao: str) -> bool:
    if AMBIENTE == "producao":
        pass
    else:
        logger.info("SMS simulado enviado", extra={"para": telefone, "mensagem": mensagem})
        return True


async def _enviar_push(token_push: str, titulo: str, mensagem: str, id_notificacao: str) -> bool:
    if AMBIENTE == "producao":
        pass
    else:
        logger.info("Push simulado enviado", extra={"titulo": titulo, "mensagem": mensagem})
        return True


def _obter_template_rota(requisicao: Request) -> str:
    rota = requisicao.scope.get("route")
    return rota.path if rota and getattr(rota, "path", None) else requisicao.url.path
