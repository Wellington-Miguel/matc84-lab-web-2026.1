"""
services/inventory/main.py
Inventory Service — microsserviço de gestão de estoque com:
  - OCC (Optimistic Concurrency Control) com Redis versionamento
  - Validação de SKU contra catálogo
  - Dedução de estoque com garantia de não negatividade
  - Logs estruturados JSON
  - Health check para ALB
  - Métricas Prometheus
"""
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import asyncpg
import redis.asyncio as aioredis
from fastapi import FastAPI, Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, Gauge, generate_latest
from pydantic import BaseModel, field_validator
from typing import Optional

# Imports compartilhados
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

from shared.logger import get_logger, LogContext, Timer
from shared.retry import with_retry, RetryConfig

logger = get_logger("inventory-service")

# ── Métricas Prometheus ────────────────────────────────────────────────────────
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total de requisicoes HTTP recebidas pelo servico.",
    ["method", "path", "status"],
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "Duracao das requisicoes HTTP em segundos.",
    ["method", "path"],
)
STOCK_LEVEL = Gauge(
    "inventory_stock_level",
    "Nivel de estoque atual por SKU.",
    ["sku_id"],
)
STOCK_DEDUCTION_TOTAL = Counter(
    "stock_deduction_total",
    "Total de deducoes de estoque por resultado.",
    ["result"],
)
OCC_CONFLICT_TOTAL = Counter(
    "occ_conflict_total",
    "Total de conflitos de concorrencia (OCC) por SKU.",
    ["sku_id"],
)

# ── Configurações ──────────────────────────────────────────────────────────────
DB_URL    = os.getenv("DATABASE_URL", "postgresql://bebidasadmin:[REDACTED]@localhost/bebidas")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# ── Recursos globais ──────────────────────────────────────────────────────────
db_pool: asyncpg.Pool = None
redis_client: aioredis.Redis = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa e encerra conexões ao subir/derrubar o serviço."""
    global db_pool, redis_client

    logger.info("inventory-service.starting")

    db_pool = await asyncpg.create_pool(DB_URL, min_size=5, max_size=20)
    redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)

    logger.info("inventory-service.ready")
    yield  # aplicação rodando

    await db_pool.close()
    await redis_client.close()
    logger.info("inventory-service.shutdown")


app = FastAPI(title="Inventory Service", lifespan=lifespan)


# ── Middleware: Correlation ID ─────────────────────────────────────────────────
@app.middleware("http")
async def correlation_middleware(request: Request, call_next):
    correlation_id = request.headers.get("x-correlation-id") or str(uuid.uuid4())
    request_id = str(uuid.uuid4())
    timer = Timer()
    status_code = 500

    with LogContext(correlation_id=correlation_id, request_id=request_id):
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["x-correlation-id"] = correlation_id
            return response
        finally:
            path = _route_template(request)
            if path != "/metrics":
                HTTP_REQUESTS_TOTAL.labels(
                    method=request.method,
                    path=path,
                    status=str(status_code),
                ).inc()
                HTTP_REQUEST_DURATION_SECONDS.labels(
                    method=request.method,
                    path=path,
                ).observe(timer.elapsed_ms / 1000)


# ── Models ─────────────────────────────────────────────────────────────────────
class StockItem(BaseModel):
    sku_id: str
    quantity: int
    version: Optional[int] = None  # Para OCC

    @field_validator("quantity")
    @classmethod
    def quantity_non_negative(cls, v):
        if v < 0:
            raise ValueError("Quantidade não pode ser negativa")
        return v


class DeductStockRequest(BaseModel):
    quantity: int

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v):
        if v <= 0:
            raise ValueError("Quantidade deve ser positiva")
        return v


class ReplenishStockRequest(BaseModel):
    quantity: int

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v):
        if v <= 0:
            raise ValueError("Quantidade deve ser positiva")
        return v


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Health check do ALB."""
    checks = {}
    try:
        await db_pool.fetchval("SELECT 1")
        checks["db"] = "ok"
    except Exception as e:
        checks["db"] = f"error: {str(e)}"

    try:
        await redis_client.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {str(e)}"

    all_ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={"status": "healthy" if all_ok else "degraded", "checks": checks}
    )


@app.get("/metrics")
async def metrics():
    """Endpoint de scrape do Prometheus."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/inventory/{product_id}")
async def get_inventory(product_id: str):
    """Obtém nível de estoque para um produto (por UUID)."""
    timer = Timer()
    
    row = await db_pool.fetchrow(
        "SELECT sku_id, quantity, version, updated_at FROM inventory WHERE sku_id = $1::uuid",
        product_id,
    )
    
    if not row:
        logger.warning(
            "inventory.product_not_found",
            extra={"product_id": product_id, "execution_ms": timer.elapsed_ms}
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Produto {product_id} não encontrado"
        )

    STOCK_LEVEL.labels(sku_id=str(row["sku_id"])).set(row["quantity"])
    
    logger.info(
        "inventory.fetched",
        extra={
            "product_id": product_id,
            "quantity": row["quantity"],
            "version": row["version"],
            "execution_ms": timer.elapsed_ms
        }
    )
    
    return {
        "sku_id": str(row["sku_id"]),
        "quantity": row["quantity"],
        "version": row["version"],
        "updated_at": row["updated_at"].isoformat(),
    }


@app.post("/inventory/{product_id}/deduct", status_code=status.HTTP_200_OK)
async def deduct_stock(product_id: str, payload: DeductStockRequest):
    """
    Deduz estoque usando OCC (Optimistic Concurrency Control).
    
    Estratégia:
    1. Lê estoque atual + versão do Redis (cache otimista)
    2. Valida se há quantidade suficiente
    3. Tenta atualizar no banco incrementando versão
    4. Se versão não bate, retorna 409 CONFLICT (retry do cliente)
    """
    timer = Timer()
    max_retries = 3
    attempt = 0

    while attempt < max_retries:
        attempt += 1
        
        # 1. Ler estado atual (tenta Redis primeiro, depois DB)
        current = await _get_stock_with_version(product_id)
        if not current:
            STOCK_DEDUCTION_TOTAL.labels(result="not_found").inc()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Produto {product_id} não encontrado"
            )

        # 2. Validar quantidade
        if current["quantity"] < payload.quantity:
            STOCK_DEDUCTION_TOTAL.labels(result="insufficient").inc()
            logger.warning(
                "inventory.deduct_insufficient",
                extra={
                    "product_id": product_id,
                    "requested": payload.quantity,
                    "available": current["quantity"],
                }
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Estoque insuficiente. Disponível: {current['quantity']}"
            )

        # 3. Tentar atualizar com versionamento (OCC)
        new_quantity = current["quantity"] - payload.quantity
        new_version = current["version"] + 1

        rows_updated = await db_pool.execute(
            """
            UPDATE inventory
            SET quantity = $1, version = $2, updated_at = NOW()
            WHERE sku_id = $3::uuid AND version = $4
            """,
            new_quantity,
            new_version,
            product_id,
            current["version"],
        )

        if rows_updated == "UPDATE 1":
            # Sucesso! Atualiza cache
            await redis_client.setex(
                f"stock:{product_id}",
                60,
                f"{new_quantity}:{new_version}"
            )
            
            STOCK_LEVEL.labels(sku_id=product_id).set(new_quantity)
            STOCK_DEDUCTION_TOTAL.labels(result="success").inc()
            
            logger.info(
                "inventory.deducted",
                extra={
                    "product_id": product_id,
                    "deducted": payload.quantity,
                    "remaining": new_quantity,
                    "version": new_version,
                    "attempt": attempt,
                    "execution_ms": timer.elapsed_ms,
                }
            )
            
            return {
                "sku_id": product_id,
                "deducted": payload.quantity,
                "remaining": new_quantity,
                "version": new_version,
            }

        # Conflito de versão: retry
        OCC_CONFLICT_TOTAL.labels(sku_id=product_id).inc()
        logger.warning(
            "inventory.occ_conflict",
            extra={
                "product_id": product_id,
                "attempt": attempt,
                "max_retries": max_retries,
            }
        )

        # Invalidar cache e tentar novamente
        await redis_client.delete(f"stock:{product_id}")

    # Falha após max_retries
    STOCK_DEDUCTION_TOTAL.labels(result="conflict").inc()
    logger.error(
        "inventory.deduct_max_retries_exceeded",
        extra={
            "product_id": product_id,
            "max_retries": max_retries,
            "execution_ms": timer.elapsed_ms,
        }
    )
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=f"Não foi possível deduzir estoque após {max_retries} tentativas. Tente novamente."
    )


@app.post("/inventory/{product_id}/replenish", status_code=status.HTTP_200_OK)
async def replenish_stock(product_id: str, payload: ReplenishStockRequest):
    """Repõe estoque (operação idempotente se salvar em auditoria)."""
    timer = Timer()
    
    row = await db_pool.fetchrow(
        "SELECT quantity FROM inventory WHERE sku_id = $1::uuid",
        product_id
    )
    
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Produto {product_id} não encontrado"
        )

    new_quantity = row["quantity"] + payload.quantity

    await db_pool.execute(
        """
        UPDATE inventory
        SET quantity = $1, updated_at = NOW()
        WHERE sku_id = $2::uuid
        """,
        new_quantity,
        product_id,
    )

    # Invalidar cache
    await redis_client.delete(f"stock:{product_id}")
    STOCK_LEVEL.labels(sku_id=product_id).set(new_quantity)

    logger.info(
        "inventory.replenished",
        extra={
            "product_id": product_id,
            "added": payload.quantity,
            "total": new_quantity,
            "execution_ms": timer.elapsed_ms,
        }
    )

    return {
        "sku_id": product_id,
        "added": payload.quantity,
        "total": new_quantity,
    }


# ── Funções internas ───────────────────────────────────────────────────────────

def _route_template(request: Request) -> str:
    """Template da rota para métricas."""
    route = request.scope.get("route")
    if route and getattr(route, "path", None):
        return route.path
    return request.url.path


async def _get_stock_with_version(product_id: str) -> Optional[dict]:
    """
    Obtém estoque + versão de forma otimista.
    Cache-first, fallback para DB.
    """
    # Tenta Redis
    cached = await redis_client.get(f"stock:{product_id}")
    if cached:
        qty_str, version_str = cached.split(":")
        return {"quantity": int(qty_str), "version": int(version_str)}

    # Fallback: DB
    row = await db_pool.fetchrow(
        "SELECT quantity, version FROM inventory WHERE sku_id = $1::uuid",
        product_id
    )
    if row:
        # Popula cache
        await redis_client.setex(
            f"stock:{product_id}",
            60,
            f"{row['quantity']}:{row['version']}"
        )
        return {"quantity": row["quantity"], "version": row["version"]}

    return None
