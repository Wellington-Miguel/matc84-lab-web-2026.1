"""
services/order/main.py
Order Service — microsserviço de pedidos com:
  - Idempotência obrigatória (Idempotency-Key no header)
  - Validação de estoque via Redis (OCC)
  - Publicação assíncrona no SQS (SBA pattern)
  - Logs estruturados JSON
  - Health check para ALB
"""
import os
import uuid
import json
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import asyncpg
import redis.asyncio as aioredis
import boto3
from fastapi import FastAPI, Request, Response, Header, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator
from typing import Optional

# Imports compartilhados (ajuste o PYTHONPATH ao rodar)
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

from shared.logger import get_logger, LogContext, Timer
from shared.idempotency import IdempotencyGuard
from shared.retry import with_retry, RetryConfig

logger = get_logger("order-service")

# ── Configurações (via variáveis de ambiente) ─────────────────────────────────
DB_URL       = os.getenv("DATABASE_URL", "postgresql://bebidasadmin:senha@localhost/bebidas")
REDIS_URL    = os.getenv("REDIS_URL", "redis://localhost:6379")
SQS_QUEUE    = os.getenv("SQS_ORDER_QUEUE_URL", "")
AWS_REGION   = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

# ── Recursos globais ──────────────────────────────────────────────────────────
db_pool: asyncpg.Pool = None
redis_client: aioredis.Redis = None
sqs_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa e encerra conexões ao subir/derrubar o serviço."""
    global db_pool, redis_client, sqs_client

    logger.info("order-service.starting")

    db_pool = await asyncpg.create_pool(DB_URL, min_size=5, max_size=20)
    redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
    sqs_client = boto3.client("sqs", region_name=AWS_REGION)

    logger.info("order-service.ready")
    yield  # aplicação rodando

    await db_pool.close()
    await redis_client.close()
    logger.info("order-service.shutdown")


app = FastAPI(title="Order Service", lifespan=lifespan)


# ── Middleware: correlation ID propagado a todos os logs ───────────────────────
@app.middleware("http")
async def correlation_middleware(request: Request, call_next):
    correlation_id = request.headers.get("x-correlation-id") or str(uuid.uuid4())
    request_id = str(uuid.uuid4())

    with LogContext(correlation_id=correlation_id, request_id=request_id):
        response = await call_next(request)
        response.headers["x-correlation-id"] = correlation_id
        return response


# ── Models ────────────────────────────────────────────────────────────────────
class OrderItem(BaseModel):
    sku_id: str
    quantity: int
    unit_price: float

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v):
        if v <= 0:
            raise ValueError("Quantidade deve ser positiva")
        return v


class CreateOrderRequest(BaseModel):
    customer_id: str
    items: list[OrderItem]

    @property
    def total(self) -> float:
        return round(sum(i.quantity * i.unit_price for i in self.items), 2)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Health check do ALB — deve responder 200 em < 5s."""
    checks = {}
    try:
        await db_pool.fetchval("SELECT 1")
        checks["db"] = "ok"
    except Exception:
        checks["db"] = "error"

    try:
        await redis_client.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"

    all_ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={"status": "healthy" if all_ok else "degraded", "checks": checks}
    )


@app.post("/orders", status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: CreateOrderRequest,
    idempotency_key: Optional[str] = Header(None, alias="idempotency-key"),
):
    """
    Cria um pedido com garantia de execução única.

    Header obrigatório: Idempotency-Key (UUID gerado pelo cliente)
    """
    timer = Timer()
    key = idempotency_key or str(uuid.uuid4())

    # 1. Verificar estoque no Redis (OCC)
    for item in payload.items:
        available = await _check_stock(item.sku_id, item.quantity)
        if not available:
            logger.warning("order.stock_insufficient", sku_id=item.sku_id, quantity=item.quantity)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Estoque insuficiente para SKU {item.sku_id}"
            )

    # 2. Criar pedido com idempotência garantida
    guard = IdempotencyGuard(db_pool)

    try:
        order = await guard.execute(
            key=key,
            operation=lambda: _persist_order(payload),
        )
    except Exception as err:
        logger.error(
            "order.create_failed",
            error_type=type(err).__name__,
            execution_ms=timer.elapsed_ms,
            status="error",
        )
        raise HTTPException(status_code=500, detail="Erro interno ao criar pedido")

    # 3. Publicar no SQS (assíncrono — não bloqueia resposta)
    asyncio.create_task(_publish_to_sqs(order))

    logger.info(
        "order.created",
        order_id=order["id"],
        customer_id=payload.customer_id,
        total=payload.total,
        execution_ms=timer.elapsed_ms,
        status="success",
    )

    return order


@app.get("/orders/{order_id}")
async def get_order(order_id: str):
    """Busca pedido por ID — lê da réplica de leitura."""
    row = await db_pool.fetchrow(
        "SELECT * FROM orders WHERE id = $1",
        order_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")

    return dict(row)


# ── Funções internas ──────────────────────────────────────────────────────────

async def _check_stock(sku_id: str, quantity: int) -> bool:
    """
    Verifica estoque no Redis (Data Grid do SBA).
    TTL curto (30s) para inventário — aceitamos consistência eventual aqui.
    """
    raw = await redis_client.get(f"stock:{sku_id}")
    if raw is None:
        # Cache miss: busca do banco e repopula Redis
        row = await db_pool.fetchrow("SELECT quantity FROM inventory WHERE sku_id = $1", sku_id)
        if not row:
            return False
        stock = row["quantity"]
        await redis_client.setex(f"stock:{sku_id}", 30, str(stock))
    else:
        stock = int(raw)

    return stock >= quantity


async def _persist_order(payload: CreateOrderRequest) -> dict:
    """Persiste pedido no banco dentro de uma transação."""
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            order_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)

            await conn.execute(
                """
                INSERT INTO orders (id, customer_id, total, status, created_at)
                VALUES ($1, $2, $3, 'pending', $4)
                """,
                order_id, payload.customer_id, payload.total, now,
            )

            for item in payload.items:
                await conn.execute(
                    """
                    INSERT INTO order_items (order_id, sku_id, quantity, unit_price)
                    VALUES ($1, $2, $3, $4)
                    """,
                    order_id, item.sku_id, item.quantity, item.unit_price,
                )

    return {
        "id": order_id,
        "customer_id": payload.customer_id,
        "total": payload.total,
        "status": "pending",
        "created_at": now.isoformat(),
    }


async def _publish_to_sqs(order: dict):
    """
    Publica pedido no SQS para processamento assíncrono (Data Pump).
    Usa retry com backoff para garantir entrega.
    """
    if not SQS_QUEUE:
        return

    message = {
        "orderId": order["id"],
        "customerId": order["customer_id"],
        "total": order["total"],
        "idempotencyKey": str(uuid.uuid4()),
    }

    async def send():
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: sqs_client.send_message(
                QueueUrl=SQS_QUEUE,
                MessageBody=json.dumps(message),
                MessageGroupId=order["customer_id"],        # FIFO grouping
                MessageDeduplicationId=order["id"],         # deduplicação FIFO
            )
        )

    try:
        await with_retry(send, config=RetryConfig(max_attempts=3, base_delay=1.0))
        logger.info("order.sqs_published", order_id=order["id"])
    except Exception as err:
        # Falha no SQS não cancela o pedido — o dado já foi salvo no banco
        logger.error("order.sqs_publish_failed", order_id=order["id"], error=str(err))
