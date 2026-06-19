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
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel, field_validator
from typing import Optional

# Imports compartilhados (ajuste o PYTHONPATH ao rodar)
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

from shared.logger import get_logger, LogContext, Timer
from shared.idempotency import IdempotencyGuard
from shared.retry import with_retry, RetryConfig

logger = get_logger("order-service")

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
ORDER_CREATION_TOTAL = Counter(
    "order_creation_total",
    "Total de tentativas de criacao de pedido por resultado.",
    ["result"],
)
STOCK_CHECK_TOTAL = Counter(
    "stock_check_total",
    "Total de verificacoes de estoque por resultado.",
    ["result"],
)
SQS_PUBLISH_TOTAL = Counter(
    "sqs_publish_total",
    "Total de publicacoes de pedidos no SQS por resultado.",
    ["result"],
)

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

    @field_validator("unit_price")
    @classmethod
    def price_positive(cls, v):
        if v <= 0:
            raise ValueError("Unit price deve ser positivo")
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


@app.get("/metrics")
async def metrics():
    """Endpoint de scrape do Prometheus."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


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
    # key = idempotency_key or str(uuid.uuid4())
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Header idempotency-key é obrigatório"
        )
    key = IdempotencyGuard.validate_key(idempotency_key)

    # 1. Verificar estoque no Redis (OCC)
    for item in payload.items:
        available = await _check_stock(item.sku_id, item.quantity)
        if not available:
            ORDER_CREATION_TOTAL.labels(result="stock_insufficient").inc()
            logger.warning(
                "order.stock_insufficient",
                extra={
                    "sku_id": item.sku_id,
                    "quantity": item.quantity,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Estoque insuficiente para SKU {item.sku_id}"
            )

    # 2. Criar pedido com idempotência garantida
    guard = IdempotencyGuard(db_pool)

    try:
        order = await guard.execute(
            key=key,
            operation=lambda conn: _persist_order(
                conn,
                payload,
            ),
        )
    except Exception as err:
        logger.error(
            "order.create_failed",
            extra={
                "error_type": type(err).__name__,
                "execution_ms": timer.elapsed_ms,
                "status": "error",
            },
        )
        ORDER_CREATION_TOTAL.labels(result="error").inc()
        raise HTTPException(status_code=500, detail="Erro interno ao criar pedido")

    # 3. Publicar no SQS (assíncrono — não bloqueia resposta)
    asyncio.create_task(_publish_to_sqs(order))

    logger.info(
        "order.created",
        extra={
            "order_id": order["id"],
            "customer_id": payload.customer_id,
            "total": payload.total,
            "execution_ms": timer.elapsed_ms,
            "status": "success",
        },
    )
    ORDER_CREATION_TOTAL.labels(result="success").inc()

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

def _route_template(request: Request) -> str:
    """Retorna o template da rota para evitar cardinalidade alta nas metricas."""
    route = request.scope.get("route")
    if route is not None and getattr(route, "path", None):
        return route.path
    return request.url.path


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
            STOCK_CHECK_TOTAL.labels(result="not_found").inc()
            return False
        stock = row["quantity"]
        await redis_client.setex(f"stock:{sku_id}", 30, str(stock))
    else:
        stock = int(raw)

    if stock >= quantity:
        STOCK_CHECK_TOTAL.labels(result="available").inc()
        return True

    STOCK_CHECK_TOTAL.labels(result="insufficient").inc()
    return False


# apenas usar a conexão recebida:
async def _persist_order(
    conn: asyncpg.Connection,
    payload: CreateOrderRequest,
) -> dict:
    """
    Persiste o pedido usando uma conexão já aberta
    pelo IdempotencyGuard.
    """

    order_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    await conn.execute(
        """
        INSERT INTO orders
            (id, customer_id, total, status, created_at)
        VALUES
            ($1, $2, $3, 'pending', $4)
        """,
        order_id,
        payload.customer_id,
        payload.total,
        now,
    )

    for item in payload.items:

        await conn.execute(
            """
            INSERT INTO order_items
                (order_id, sku_id, quantity, unit_price)
            VALUES
                ($1, $2, $3, $4)
            """,
            order_id,
            item.sku_id,
            item.quantity,
            item.unit_price,
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
        SQS_PUBLISH_TOTAL.labels(result="skipped").inc()
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
        SQS_PUBLISH_TOTAL.labels(result="success").inc()
        logger.info("order.sqs_published", extra={"order_id": order["id"]})
    except Exception as err:
        # Falha no SQS não cancela o pedido — o dado já foi salvo no banco
        SQS_PUBLISH_TOTAL.labels(result="error").inc()
        logger.error(
            "order.sqs_publish_failed",
            extra={"order_id": order["id"], "error": str(err)},
        )
