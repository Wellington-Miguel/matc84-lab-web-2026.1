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

# Imports compartilhados 
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

from shared.logger import get_logger, LogContext, Timer
from shared.idempotency import IdempotencyGuard
from shared.retry import with_retry, RetryConfig

logger = get_logger("order-service")

REQUISICOES_HTTP_TOTAL = Counter(
    "http_requests_total",
    "Total de requisicoes HTTP recebidas pelo servico.",
    ["method", "path", "status"],
)
DURACAO_REQUISICOES_SEGUNDOS = Histogram(
    "http_request_duration_seconds",
    "Duracao das requisicoes HTTP em segundos.",
    ["method", "path"],
)
CRIACAO_PEDIDOS_TOTAL = Counter(
    "order_creation_total",
    "Total de tentativas de criacao de pedido por resultado.",
    ["result"],
)
VERIFICACAO_ESTOQUE_TOTAL = Counter(
    "stock_check_total",
    "Total de verificacoes de estoque por resultado.",
    ["result"],
)
PUBLICACAO_SQS_TOTAL = Counter(
    "sqs_publish_total",
    "Total de publicacoes de pedidos no SQS por resultado.",
    ["result"],
)

# Configurações
URL_BD       = os.getenv("DATABASE_URL", "postgresql://bebidasadmin:senha@localhost/bebidas")
URL_REDIS    = os.getenv("REDIS_URL", "redis://localhost:6379")
FILA_SQS     = os.getenv("SQS_ORDER_QUEUE_URL", "")
REGIAO_AWS   = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

#Recursos globais
pool_bd: asyncpg.Pool = None
cliente_redis: aioredis.Redis = None
cliente_sqs = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa e encerra conexões ao subir/derrubar o serviço."""
    global pool_bd, cliente_redis, cliente_sqs

    logger.info("order-service.starting")

    pool_bd = await asyncpg.create_pool(URL_BD, min_size=5, max_size=20)
    cliente_redis = aioredis.from_url(URL_REDIS, decode_responses=True)
    cliente_sqs = boto3.client(
        "sqs",
        region_name=REGIAO_AWS,
        endpoint_url=os.getenv("AWS_ENDPOINT_URL"),
    )

    logger.info("order-service.ready")
    yield  

    await pool_bd.close()
    await cliente_redis.close()
    logger.info("order-service.shutdown")


app = FastAPI(title="Order Service", lifespan=lifespan)


# Middleware
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
            caminho = _route_template(requisicao)
            if caminho != "/metrics":
                REQUISICOES_HTTP_TOTAL.labels(
                    method=requisicao.method,
                    path=caminho,
                    status=str(codigo_status),
                ).inc()
                DURACAO_REQUISICOES_SEGUNDOS.labels(
                    method=requisicao.method,
                    path=caminho,
                ).observe(cronometro.elapsed_ms / 1000)


# Models
class ItemPedido(BaseModel):
    sku_id: str
    quantity: int
    unit_price: float

    @field_validator("quantity")
    @classmethod
    def quantidade_positiva(cls, v):
        if v <= 0:
            raise ValueError("Quantidade deve ser positiva")
        return v

    @field_validator("unit_price")
    @classmethod
    def preco_positivo(cls, v):
        if v <= 0:
            raise ValueError("Unit price deve ser positivo")
        return v


class RequisicaoCriarPedido(BaseModel):
    customer_id: str
    items: list[ItemPedido]

    @property
    def total(self) -> float:
        return round(sum(i.quantity * i.unit_price for i in self.items), 2)


CreateOrderRequest = RequisicaoCriarPedido
OrderItem = ItemPedido


#Endpoints

@app.get("/health")
async def verificacao_saude():
    """Health check do ALB — deve responder 200 em < 5s."""
    checks = {}
    try:
        await pool_bd.fetchval("SELECT 1")
        checks["db"] = "ok"
    except Exception:
        checks["db"] = "error"

    try:
        await cliente_redis.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"

    all_ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={"status": "healthy" if all_ok else "degraded", "checks": checks}
    )


@app.get("/metrics")
async def metricas():
    """Endpoint de scrape do Prometheus."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/orders", status_code=status.HTTP_201_CREATED)
async def criar_pedido(
    requisicao: RequisicaoCriarPedido,
    chave_idempotencia: Optional[str] = Header(None, alias="idempotency-key"),
):
    """
    Cria um pedido com garantia de execução única.

    Header obrigatório: Idempotency-Key (UUID gerado pelo cliente)
    """
    cronometro = Timer()
    if not chave_idempotencia:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Header idempotency-key é obrigatório"
        )
    chave = IdempotencyGuard.validate_key(chave_idempotencia)

    for item in requisicao.items:
        disponivel = await _verificar_estoque(item.sku_id, item.quantity)
        if not disponivel:
            CRIACAO_PEDIDOS_TOTAL.labels(result="stock_insufficient").inc()
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

    guard = IdempotencyGuard(pool_bd)

    try:
        pedido = await guard.execute(
            key=chave,
            operation=lambda conn: _persistir_pedido(
                conn,
                requisicao,
            ),
        )
    except Exception as err:
        logger.error(
            "order.create_failed",
            extra={
                "error_type": type(err).__name__,
                "execution_ms": cronometro.elapsed_ms,
                "status": "error",
            },
        )
        CRIACAO_PEDIDOS_TOTAL.labels(result="error").inc()
        raise HTTPException(status_code=500, detail="Erro interno ao criar pedido")

    asyncio.create_task(_publicar_na_sqs(pedido))

    logger.info(
        "order.created",
        extra={
            "order_id": pedido["id"],
            "customer_id": requisicao.customer_id,
            "total": requisicao.total,
            "execution_ms": cronometro.elapsed_ms,
            "status": "success",
        },
    )
    CRIACAO_PEDIDOS_TOTAL.labels(result="success").inc()

    return pedido


@app.get("/orders/{order_id}")
async def obter_pedido(order_id: str):
    """Busca pedido por ID — lê da réplica de leitura."""
    linha = await pool_bd.fetchrow(
        "SELECT * FROM orders WHERE id = $1",
        order_id,
    )
    if not linha:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")

    return dict(linha)


#Funções internas 

def _route_template(request: Request) -> str:
    """Retorna o template da rota para evitar cardinalidade alta nas metricas."""
    route = request.scope.get("route")
    if route is not None and getattr(route, "path", None):
        return route.path
    return request.url.path


async def _verificar_estoque(sku_id: str, quantity: int) -> bool:
    """
    Verifica estoque no Redis (Data Grid do SBA).
    TTL curto (30s) para inventário — aceitamos consistência eventual aqui.
    """
    raw = await cliente_redis.get(f"stock:{sku_id}")
    if raw is None:
        linha = await pool_bd.fetchrow("SELECT quantity FROM inventory WHERE sku_id = $1", sku_id)
        if not linha:
            VERIFICACAO_ESTOQUE_TOTAL.labels(result="not_found").inc()
            return False
        stock = linha["quantity"]
        await cliente_redis.setex(f"stock:{sku_id}", 30, str(stock))
    else:
        stock = int(raw)

    if stock >= quantity:
        VERIFICACAO_ESTOQUE_TOTAL.labels(result="available").inc()
        return True

    VERIFICACAO_ESTOQUE_TOTAL.labels(result="insufficient").inc()
    return False


#conexão recebida
async def _persistir_pedido(
    conn: asyncpg.Connection,
    requisicao: RequisicaoCriarPedido,
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
        requisicao.customer_id,
        requisicao.total,
        now,
    )

    for item in requisicao.items:

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
        "customer_id": requisicao.customer_id,
        "total": requisicao.total,
        "status": "pending",
        "created_at": now.isoformat(),
    }


async def _publicar_na_sqs(pedido: dict):
    """
    Publica pedido no SQS para processamento assíncrono (Data Pump).
    Usa retry com backoff para garantir entrega.
    """
    if not FILA_SQS:
        PUBLICACAO_SQS_TOTAL.labels(result="skipped").inc()
        return

    message = {
        "eventType": "pedido.criado",
        "pedidoId": pedido["id"],
        "clienteId": pedido["customer_id"],
        "total": pedido["total"],
    }

    async def send():
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: cliente_sqs.send_message(
                QueueUrl=FILA_SQS,
                MessageBody=json.dumps(message),
                MessageGroupId=pedido["customer_id"],      
                MessageDeduplicationId=pedido["id"],         
            )
        )

    try:
        await with_retry(send, config=RetryConfig(max_attempts=3, base_delay=1.0))
        PUBLICACAO_SQS_TOTAL.labels(result="success").inc()
        logger.info("order.sqs_published", extra={"order_id": pedido["id"]})
    except Exception as err:
        PUBLICACAO_SQS_TOTAL.labels(result="error").inc()
        logger.error(
            "order.sqs_publish_failed",
            extra={"order_id": pedido["id"], "error": str(err)},
        )
