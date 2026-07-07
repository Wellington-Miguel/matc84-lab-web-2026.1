import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

import asyncpg
import redis.asyncio as aioredis
from fastapi import FastAPI, Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, Gauge, generate_latest
from pydantic import BaseModel, field_validator

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

from shared.logger import get_logger, LogContext, Timer

logger = get_logger("inventory-service")

# Métricas
REQUISICOES_TOTAL = Counter("http_requests_total", "Requisições HTTP", ["metodo", "caminho", "status"])
DURACAO_REQUISICOES = Histogram("http_request_duration_seconds", "Duração requisição", ["metodo", "caminho"])
NIVEL_ESTOQUE = Gauge("inventory_stock_level", "Nível de estoque", ["id_sku"])
DEDUCOES_TOTAL = Counter("stock_deduction_total", "Deduções de estoque", ["resultado"])
CONFLITOS_OCC = Counter("occ_conflict_total", "Conflitos OCC", ["id_sku"])

# Configuração
URL_BD = os.getenv("DATABASE_URL", "postgresql://bebidasadmin:[REDACTED]@localhost/bebidas")
URL_REDIS = os.getenv("REDIS_URL", "redis://localhost:6379")

# Globais
pool_bd: asyncpg.Pool = None
cliente_redis: aioredis.Redis = None


@asynccontextmanager
async def ciclo_vida(app: FastAPI):
    global pool_bd, cliente_redis
    logger.info("inventory-service.iniciando")
    
    pool_bd = await asyncpg.create_pool(URL_BD, min_size=5, max_size=20)
    cliente_redis = aioredis.from_url(URL_REDIS, decode_responses=True)
    
    logger.info("inventory-service.pronto")
    yield
    
    await pool_bd.close()
    await cliente_redis.close()
    logger.info("inventory-service.encerrando")


app = FastAPI(title="Inventory Service", lifespan=ciclo_vida)


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
class RequisicaoDeduzirEstoque(BaseModel):
    quantidade: int
    
    @field_validator("quantidade")
    @classmethod
    def validar_quantidade(cls, v):
        if v <= 0:
            raise ValueError("Quantidade deve ser positiva")
        return v


class RequisicaoReporEstoque(BaseModel):
    quantidade: int
    
    @field_validator("quantidade")
    @classmethod
    def validar_quantidade(cls, v):
        if v <= 0:
            raise ValueError("Quantidade deve ser positiva")
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
        await cliente_redis.ping()
        verificacoes["redis"] = "ok"
    except Exception as e:
        verificacoes["redis"] = f"erro: {str(e)}"

    tudo_ok = all(v == "ok" for v in verificacoes.values())
    return JSONResponse(
        status_code=200 if tudo_ok else 503,
        content={"status": "saudavel" if tudo_ok else "degradado", "verificacoes": verificacoes}
    )


@app.get("/metrics")
async def metricas():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/estoque/{id_produto}")
async def obter_estoque(id_produto: str):
    cronometro = Timer()
    linha = await pool_bd.fetchrow(
        "SELECT sku_id, quantity, version, updated_at FROM inventory WHERE sku_id = $1::uuid",
        id_produto,
    )
    
    if not linha:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    NIVEL_ESTOQUE.labels(id_sku=str(linha["sku_id"])).set(linha["quantity"])
    logger.info("estoque.obter", extra={"id_produto": id_produto, "tempo_ms": cronometro.elapsed_ms})
    
    return {
        "id_sku": str(linha["sku_id"]),
        "quantidade": linha["quantity"],
        "versao": linha["version"],
        "data_atualizacao": linha["updated_at"].isoformat(),
    }


@app.post("/estoque/{id_produto}/deduzir", status_code=200)
async def deduzir_estoque(id_produto: str, requisicao: RequisicaoDeduzirEstoque):
    cronometro = Timer()
    max_tentativas = 3
    tentativa = 0

    while tentativa < max_tentativas:
        tentativa += 1
        estoque_atual = await _obter_estoque_com_versao(id_produto)
        
        if not estoque_atual:
            DEDUCOES_TOTAL.labels(resultado="nao_encontrado").inc()
            raise HTTPException(status_code=404, detail="Produto não encontrado")

        if estoque_atual["quantidade"] < requisicao.quantidade:
            DEDUCOES_TOTAL.labels(resultado="insuficiente").inc()
            raise HTTPException(status_code=409, detail=f"Estoque insuficiente: {estoque_atual['quantidade']} disponível")

        nova_quantidade = estoque_atual["quantidade"] - requisicao.quantidade
        nova_versao = estoque_atual["versao"] + 1

        linhas_atualizadas = await pool_bd.execute(
            "UPDATE inventory SET quantity = $1, version = $2, updated_at = NOW() WHERE sku_id = $3::uuid AND version = $4",
            nova_quantidade, nova_versao, id_produto, estoque_atual["versao"],
        )

        if linhas_atualizadas == "UPDATE 1":
            await cliente_redis.setex(f"estoque:{id_produto}", 60, f"{nova_quantidade}:{nova_versao}")
            NIVEL_ESTOQUE.labels(id_sku=id_produto).set(nova_quantidade)
            DEDUCOES_TOTAL.labels(resultado="sucesso").inc()
            
            logger.info("estoque.deduzido", extra={
                "id_produto": id_produto, "deduzido": requisicao.quantidade,
                "restante": nova_quantidade, "tentativa": tentativa, "tempo_ms": cronometro.elapsed_ms
            })
            
            return {"id_sku": id_produto, "deduzido": requisicao.quantidade, "restante": nova_quantidade, "versao": nova_versao}

        CONFLITOS_OCC.labels(id_sku=id_produto).inc()
        await cliente_redis.delete(f"estoque:{id_produto}")

    DEDUCOES_TOTAL.labels(resultado="conflito").inc()
    raise HTTPException(status_code=409, detail=f"Falha após {max_tentativas} tentativas")


@app.post("/estoque/{id_produto}/repor", status_code=200)
async def repor_estoque(id_produto: str, requisicao: RequisicaoReporEstoque):
    cronometro = Timer()
    linha = await pool_bd.fetchrow("SELECT quantity FROM inventory WHERE sku_id = $1::uuid", id_produto)
    
    if not linha:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    nova_quantidade = linha["quantity"] + requisicao.quantidade
    await pool_bd.execute("UPDATE inventory SET quantity = $1, updated_at = NOW() WHERE sku_id = $2::uuid", nova_quantidade, id_produto)

    await cliente_redis.delete(f"estoque:{id_produto}")
    NIVEL_ESTOQUE.labels(id_sku=id_produto).set(nova_quantidade)

    logger.info("estoque.repor", extra={"id_produto": id_produto, "adicionado": requisicao.quantidade, "tempo_ms": cronometro.elapsed_ms})

    return {"id_sku": id_produto, "adicionado": requisicao.quantidade, "total": nova_quantidade}


def _obter_template_rota(requisicao: Request) -> str:
    rota = requisicao.scope.get("route")
    return rota.path if rota and getattr(rota, "path", None) else requisicao.url.path


async def _obter_estoque_com_versao(id_produto: str) -> Optional[dict]:
    em_cache = await cliente_redis.get(f"estoque:{id_produto}")
    if em_cache:
        qty_str, versao_str = em_cache.split(":")
        return {"quantidade": int(qty_str), "versao": int(versao_str)}

    linha = await pool_bd.fetchrow("SELECT quantity, version FROM inventory WHERE sku_id = $1::uuid", id_produto)
    if linha:
        await cliente_redis.setex(f"estoque:{id_produto}", 60, f"{linha['quantity']}:{linha['version']}")
        return {"quantidade": linha["quantity"], "versao": linha["version"]}

    return None
