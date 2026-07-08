"""
services/payment/main.py
Payment Service — microsserviço de pagamentos com:
  - Idempotência obrigatória (evita cobrança dupla)
  - Logs estruturados JSON
  - Health check para ALB
"""
import os
import uuid
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

import asyncpg
import boto3
import asyncio
from fastapi import FastAPI, Request, Header, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

# Imports compartilhados
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

from shared.logger import get_logger, LogContext, Timer
from shared.idempotency import IdempotencyGuard
from shared.retry import with_retry, RetryConfig

logger = get_logger("payment-service")

# Configurações 
URL_BD = os.getenv("DATABASE_URL", "postgresql://bebidasadmin:senha@localhost/bebidas")
FILA_SQS = os.getenv("SQS_ORDER_QUEUE_URL", os.getenv("SQS_NOTIFICATION_QUEUE_URL", ""))
REGIAO_AWS = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

# Recursos globais
pool_bd: asyncpg.Pool = None
cliente_sqs = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa e encerra conexões ao subir/derrubar o serviço."""
    global pool_bd, cliente_sqs

    logger.info("payment-service.starting")
    pool_bd = await asyncpg.create_pool(URL_BD, min_size=5, max_size=20)
    cliente_sqs = boto3.client(
        "sqs",
        region_name=REGIAO_AWS,
        endpoint_url=os.getenv("AWS_ENDPOINT_URL"),
    )
    logger.info("payment-service.ready")
    
    yield  

    await pool_bd.close()
    logger.info("payment-service.shutdown")

app = FastAPI(title="Payment Service", lifespan=lifespan)

# Middleware
@app.middleware("http")
async def middleware_correlacao(requisicao: Request, proximo):
    id_correlacao = requisicao.headers.get("x-correlation-id") or str(uuid.uuid4())
    id_requisicao = str(uuid.uuid4())

    with LogContext(correlation_id=id_correlacao, request_id=id_requisicao):
        resposta = await proximo(requisicao)
        resposta.headers["x-correlation-id"] = id_correlacao
        return resposta

# Models
class RequisicaoCriarPagamento(BaseModel):
    order_id: str
    amount: float
    provider_ref: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def valor_positivo(cls, v):
        if v <= 0:
            raise ValueError("Amount deve ser um valor positivo")
        return v


CreatePaymentRequest = RequisicaoCriarPagamento

# Endpoints 

@app.get("/health")
async def verificacao_saude():
    """Health check do ALB — deve responder 200 em < 5s."""
    checks = {}
    try:
        await pool_bd.fetchval("SELECT 1")
        checks["db"] = "ok"
    except Exception:
        checks["db"] = "error"

    all_ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={"status": "healthy" if all_ok else "degraded", "checks": checks}
    )

@app.post("/payments", status_code=status.HTTP_201_CREATED)
async def criar_pagamento(
    requisicao: RequisicaoCriarPagamento,
    chave_idempotencia: Optional[str] = Header(None, alias="idempotency-key"),
):
    """
    Processa um pagamento com garantia de execução única.
    """
    cronometro = Timer()
    
    if not chave_idempotencia:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Header idempotency-key é obrigatório"
        )
    chave = IdempotencyGuard.validate_key(chave_idempotencia)

    guard = IdempotencyGuard(pool_bd)

    try:
        payment = await guard.execute(
            key=chave,
            operation=lambda conn: _persistir_pagamento(conn, requisicao, chave),
        )
    except Exception as err:
        logger.error("payment.create_failed",
                    extra={
                        "error_type": type(err).__name__,
                        "execution_ms": cronometro.elapsed_ms,
                        "status": "error",
                    },
                )
        raise HTTPException(status_code=500, detail="Erro interno ao processar pagamento")

    logger.info("payment.created",
                extra={
                    "payment_id": pagamento["id"],
                    "order_id": requisicao.order_id,
                    "amount": requisicao.amount,
                    "execution_ms": cronometro.elapsed_ms,
                    "status": "success",
                })

    try:
        await _publicar_evento_pagamento(pagamento)
    except Exception as err:
        logger.error("payment.event_publish_failed",
                    extra={
                        "error_type": type(err).__name__,
                        "order_id": requisicao.order_id,
                        "execution_ms": cronometro.elapsed_ms,
                    })

    return pagamento

# Funções internas

async def _persistir_pagamento(conn: asyncpg.Connection, requisicao: RequisicaoCriarPagamento, chave_idempotencia: str) -> dict:
    payment_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    await conn.execute(
        """
        INSERT INTO payments (id, order_id, amount, status, provider_ref, idempotency_key, created_at)
        VALUES ($1, $2, $3, 'completed', $4, $5, $6)
        """,
        payment_id, requisicao.order_id, requisicao.amount, requisicao.provider_ref, chave_idempotencia, now
    )

    return {
        "id": payment_id, "order_id": requisicao.order_id, "amount": requisicao.amount,
        "status": "completed", "provider_ref": requisicao.provider_ref, "created_at": now.isoformat()
    }


async def _buscar_id_cliente(id_pedido: str) -> Optional[str]:
    linha = await pool_bd.fetchrow("SELECT customer_id FROM orders WHERE id = $1", id_pedido)
    return linha["customer_id"] if linha else None


async def _publicar_evento_pagamento(pagamento: dict):
    if not FILA_SQS:
        return

    cliente_id = await _buscar_id_cliente(pagamento["order_id"]) or "unknown"
    mensagem = {
        "eventType": "pagamento.concluido",
        "pedidoId": pagamento["order_id"],
        "clienteId": cliente_id,
        "paymentId": pagamento["id"],
        "amount": float(pagamento["amount"]),
        "providerRef": pagamento["provider_ref"],
    }

    async def send():
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: cliente_sqs.send_message(
                QueueUrl=FILA_SQS,
                MessageBody=json.dumps(mensagem),
                MessageGroupId=pagamento["order_id"],
                MessageDeduplicationId=pagamento["id"],
            )
        )

    await with_retry(send, config=RetryConfig(max_attempts=3, base_delay=1.0))