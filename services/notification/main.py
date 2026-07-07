"""
services/notification/main.py
Notification Service — microsserviço de notificações com:
  - Consumer SQS para eventos de Order, Payment, Inventory
  - Envio de email/SMS/push (mock local)
  - Rastreamento de notificações
  - Preferências de usuário
  - Métricas Prometheus
  - Health check para ALB
"""
import os
import json
import uuid
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

import asyncpg
import boto3
from fastapi import FastAPI, Request, Response, HTTPException, status, BackgroundTasks
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, Gauge, generate_latest
from pydantic import BaseModel, field_validator, EmailStr
import aiofiles

# Imports compartilhados
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

from shared.logger import get_logger, LogContext, Timer
from shared.retry import with_retry, RetryConfig

logger = get_logger("notification-service")

# ── Métricas Prometheus ────────────────────────────────────────────────────────
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total de requisicoes HTTP",
    ["method", "path", "status"],
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "Duracao das requisicoes HTTP",
    ["method", "path"],
)
NOTIFICATIONS_SENT_TOTAL = Counter(
    "notifications_sent_total",
    "Total de notificacoes enviadas por tipo",
    ["notification_type", "channel", "status"],
)
NOTIFICATIONS_QUEUED = Gauge(
    "notifications_queued",
    "Notificacoes aguardando envio",
)
SQS_EVENTS_PROCESSED = Counter(
    "sqs_events_processed_total",
    "Total de eventos SQS processados por tipo",
    ["event_type", "status"],
)

# ── Configurações ──────────────────────────────────────────────────────────────
DB_URL           = os.getenv("DATABASE_URL", "postgresql://bebidasadmin:[REDACTED]@localhost/bebidas")
SQS_QUEUE_URL    = os.getenv("SQS_NOTIFICATION_QUEUE_URL", "http://localstack:4566/000000000000/notifications.fifo")
AWS_REGION       = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
ENVIRONMENT      = os.getenv("ENVIRONMENT", "development")  # development ou production
EMAIL_FROM       = os.getenv("EMAIL_FROM", "noreply@bebidas.local")
SMS_FROM         = os.getenv("SMS_FROM", "+55 11 9999-9999")

# ── Recursos globais ──────────────────────────────────────────────────────────
db_pool: asyncpg.Pool = None
sqs_client = None
consumer_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa e encerra conexões + consumer SQS."""
    global db_pool, sqs_client, consumer_task

    logger.info("notification-service.starting", extra={"environment": ENVIRONMENT})

    db_pool = await asyncpg.create_pool(DB_URL, min_size=5, max_size=20)
    sqs_client = boto3.client("sqs", region_name=AWS_REGION)

    # Inicia consumer SQS em background
    consumer_task = asyncio.create_task(_sqs_consumer_loop())

    logger.info("notification-service.ready")
    yield  # aplicação rodando

    # Encerra consumer
    if consumer_task:
        consumer_task.cancel()
    await db_pool.close()
    logger.info("notification-service.shutdown")


app = FastAPI(title="Notification Service", lifespan=lifespan)


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

class SendNotificationRequest(BaseModel):
    recipient_id: str
    notification_type: str  # 'order_created', 'payment_completed', 'stock_alert', etc
    title: str
    message: str
    channels: list[str] = ["email"]  # email, sms, push

    @field_validator("channels")
    @classmethod
    def validate_channels(cls, v):
        valid = {"email", "sms", "push"}
        if not all(c in valid for c in v):
            raise ValueError(f"Canais válidos: {valid}")
        return v


class NotificationPreferenceRequest(BaseModel):
    recipient_id: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    push_token: Optional[str] = None
    preferences: dict = {}  # {notification_type: [channels]}

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        if v and not v.startswith("+"):
            raise ValueError("Phone deve começar com +")
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
        # Tenta fazer check SQS
        response = sqs_client.get_queue_attributes(
            QueueUrl=SQS_QUEUE_URL,
            AttributeNames=["ApproximateNumberOfMessages"]
        )
        checks["sqs"] = "ok"
        checks["queued_messages"] = int(response["Attributes"]["ApproximateNumberOfMessages"])
    except Exception as e:
        checks["sqs"] = f"error: {str(e)}"

    all_ok = all(v == "ok" for v in checks.values() if isinstance(v, str))
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={"status": "healthy" if all_ok else "degraded", "checks": checks}
    )


@app.get("/metrics")
async def metrics():
    """Endpoint Prometheus."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/notifications/send", status_code=status.HTTP_202_ACCEPTED)
async def send_notification(
    payload: SendNotificationRequest,
    background_tasks: BackgroundTasks,
):
    """
    Envia notificação imediata.
    Retorna 202 Accepted (processamento assíncrono).
    """
    timer = Timer()
    notification_id = str(uuid.uuid4())

    # 1. Persistir notificação com status 'pending'
    await db_pool.execute(
        """
        INSERT INTO notifications 
            (id, recipient_id, notification_type, title, message, channels, status, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, 'pending', NOW())
        """,
        notification_id,
        payload.recipient_id,
        payload.notification_type,
        payload.title,
        payload.message,
        json.dumps(payload.channels),
    )

    # 2. Adicionar tarefa de envio em background
    background_tasks.add_task(
        _send_notification_task,
        notification_id,
        payload.recipient_id,
        payload.channels,
        payload.title,
        payload.message,
    )

    logger.info(
        "notification.queued",
        extra={
            "notification_id": notification_id,
            "recipient_id": payload.recipient_id,
            "notification_type": payload.notification_type,
            "channels": payload.channels,
            "execution_ms": timer.elapsed_ms,
        }
    )

    NOTIFICATIONS_SENT_TOTAL.labels(
        notification_type=payload.notification_type,
        channel="queued",
        status="pending"
    ).inc()

    return {
        "notification_id": notification_id,
        "status": "pending",
        "message": "Notificação enfileirada para envio"
    }


@app.get("/notifications/{notification_id}")
async def get_notification_status(notification_id: str):
    """Obtém status de uma notificação."""
    row = await db_pool.fetchrow(
        "SELECT id, notification_type, status, channels, created_at, sent_at FROM notifications WHERE id = $1",
        notification_id
    )

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notificação {notification_id} não encontrada"
        )

    return {
        "id": row["id"],
        "notification_type": row["notification_type"],
        "status": row["status"],
        "channels": json.loads(row["channels"]),
        "created_at": row["created_at"].isoformat(),
        "sent_at": row["sent_at"].isoformat() if row["sent_at"] else None,
    }


@app.post("/preferences", status_code=status.HTTP_201_CREATED)
async def set_notification_preferences(payload: NotificationPreferenceRequest):
    """Configura preferências de notificação do usuário."""
    timer = Timer()

    await db_pool.execute(
        """
        INSERT INTO notification_preferences (recipient_id, email, phone, push_token, preferences, updated_at)
        VALUES ($1, $2, $3, $4, $5, NOW())
        ON CONFLICT (recipient_id) DO UPDATE SET
            email = EXCLUDED.email,
            phone = EXCLUDED.phone,
            push_token = EXCLUDED.push_token,
            preferences = EXCLUDED.preferences,
            updated_at = NOW()
        """,
        payload.recipient_id,
        payload.email,
        payload.phone,
        payload.push_token,
        json.dumps(payload.preferences),
    )

    logger.info(
        "notification.preferences_updated",
        extra={
            "recipient_id": payload.recipient_id,
            "channels": list(filter(None, [payload.email, payload.phone, payload.push_token])),
            "execution_ms": timer.elapsed_ms,
        }
    )

    return {
        "recipient_id": payload.recipient_id,
        "message": "Preferências atualizadas com sucesso"
    }


@app.get("/preferences/{recipient_id}")
async def get_notification_preferences(recipient_id: str):
    """Obtém preferências de notificação do usuário."""
    row = await db_pool.fetchrow(
        "SELECT recipient_id, email, phone, push_token, preferences FROM notification_preferences WHERE recipient_id = $1",
        recipient_id
    )

    if not row:
        return {
            "recipient_id": recipient_id,
            "email": None,
            "phone": None,
            "push_token": None,
            "preferences": {},
            "message": "Sem preferências configuradas"
        }

    return {
        "recipient_id": row["recipient_id"],
        "email": row["email"],
        "phone": row["phone"],
        "push_token": row["push_token"],
        "preferences": json.loads(row["preferences"]) if row["preferences"] else {},
    }


# ── Funções Internas ───────────────────────────────────────────────────────────

def _route_template(request: Request) -> str:
    """Template da rota para métricas."""
    route = request.scope.get("route")
    if route and getattr(route, "path", None):
        return route.path
    return request.url.path


async def _sqs_consumer_loop():
    """
    Loop contínuo de consumo de eventos SQS.
    Processa eventos de Order, Payment, Inventory.
    """
    logger.info("sqs_consumer.started")

    while True:
        try:
            # Recebe mensagens da fila
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: sqs_client.receive_message(
                    QueueUrl=SQS_QUEUE_URL,
                    MaxNumberOfMessages=10,
                    WaitTimeSeconds=20,  # Long polling
                )
            )

            messages = response.get("Messages", [])
            if not messages:
                continue

            for msg in messages:
                try:
                    # Parse evento
                    body = json.loads(msg["Body"])
                    event_type = body.get("eventType", "unknown")

                    # Rota para handlers específicos
                    if event_type == "order.created":
                        await _handle_order_created(body)
                    elif event_type == "payment.completed":
                        await _handle_payment_completed(body)
                    elif event_type == "payment.failed":
                        await _handle_payment_failed(body)
                    elif event_type == "stock.low":
                        await _handle_stock_low(body)
                    else:
                        logger.warning(
                            "sqs_consumer.unknown_event",
                            extra={"event_type": event_type}
                        )
                        SQS_EVENTS_PROCESSED.labels(event_type=event_type, status="unknown").inc()

                    # Delete da fila após processar
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: sqs_client.delete_message(
                            QueueUrl=SQS_QUEUE_URL,
                            ReceiptHandle=msg["ReceiptHandle"]
                        )
                    )

                    SQS_EVENTS_PROCESSED.labels(event_type=event_type, status="success").inc()

                except Exception as e:
                    logger.error(
                        "sqs_consumer.message_error",
                        extra={"error": str(e), "message_id": msg.get("MessageId")}
                    )
                    SQS_EVENTS_PROCESSED.labels(event_type="unknown", status="error").inc()

        except Exception as e:
            logger.error(
                "sqs_consumer.error",
                extra={"error": str(e)}
            )
            await asyncio.sleep(5)  # Retry após 5s


async def _handle_order_created(event: dict):
    """Handler para evento 'order.created'."""
    order_id = event.get("orderId")
    customer_id = event.get("customerId")
    total = event.get("total")

    notification_id = str(uuid.uuid4())

    await db_pool.execute(
        """
        INSERT INTO notifications 
            (id, recipient_id, notification_type, title, message, channels, status, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, 'pending', NOW())
        """,
        notification_id,
        customer_id,
        "order.created",
        "Pedido confirmado!",
        f"Seu pedido {order_id} foi confirmado. Total: R$ {total:.2f}",
        json.dumps(["email", "push"]),
    )

    # Enviar async
    await _send_notification_task(
        notification_id,
        customer_id,
        ["email", "push"],
        "Pedido confirmado!",
        f"Seu pedido {order_id} foi confirmado. Total: R$ {total:.2f}",
    )

    logger.info(
        "notification.order_created",
        extra={"order_id": order_id, "customer_id": customer_id}
    )


async def _handle_payment_completed(event: dict):
    """Handler para evento 'payment.completed'."""
    payment_id = event.get("paymentId")
    order_id = event.get("orderId")
    customer_id = event.get("customerId")

    notification_id = str(uuid.uuid4())

    await db_pool.execute(
        """
        INSERT INTO notifications 
            (id, recipient_id, notification_type, title, message, channels, status, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, 'pending', NOW())
        """,
        notification_id,
        customer_id,
        "payment.completed",
        "Pagamento aprovado!",
        f"Pagamento do pedido {order_id} foi aprovado. Seu pedido será entregue em breve.",
        json.dumps(["email", "sms", "push"]),
    )

    await _send_notification_task(
        notification_id,
        customer_id,
        ["email", "sms", "push"],
        "Pagamento aprovado!",
        f"Pagamento do pedido {order_id} foi aprovado. Seu pedido será entregue em breve.",
    )

    logger.info(
        "notification.payment_completed",
        extra={"payment_id": payment_id, "order_id": order_id}
    )


async def _handle_payment_failed(event: dict):
    """Handler para evento 'payment.failed'."""
    order_id = event.get("orderId")
    customer_id = event.get("customerId")
    reason = event.get("reason", "Motivo desconhecido")

    notification_id = str(uuid.uuid4())

    await db_pool.execute(
        """
        INSERT INTO notifications 
            (id, recipient_id, notification_type, title, message, channels, status, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, 'pending', NOW())
        """,
        notification_id,
        customer_id,
        "payment.failed",
        "Falha no pagamento",
        f"Não conseguimos processar seu pagamento. Motivo: {reason}. Por favor, tente novamente.",
        json.dumps(["email", "sms"]),
    )

    await _send_notification_task(
        notification_id,
        customer_id,
        ["email", "sms"],
        "Falha no pagamento",
        f"Não conseguimos processar seu pagamento. Motivo: {reason}. Por favor, tente novamente.",
    )

    logger.info(
        "notification.payment_failed",
        extra={"order_id": order_id, "reason": reason}
    )


async def _handle_stock_low(event: dict):
    """Handler para evento 'stock.low' (para admins)."""
    sku_id = event.get("skuId")
    current_qty = event.get("currentQuantity")
    threshold = event.get("threshold", 50)

    notification_id = str(uuid.uuid4())
    admin_id = "admin@bebidas.local"  # Em produção: buscar de LDAP/AD

    await db_pool.execute(
        """
        INSERT INTO notifications 
            (id, recipient_id, notification_type, title, message, channels, status, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, 'pending', NOW())
        """,
        notification_id,
        admin_id,
        "stock.low",
        "⚠️ Estoque Baixo",
        f"SKU {sku_id} está com apenas {current_qty} unidades (limite: {threshold}). Reposição urgente!",
        json.dumps(["email"]),
    )

    await _send_notification_task(
        notification_id,
        admin_id,
        ["email"],
        "⚠️ Estoque Baixo",
        f"SKU {sku_id} está com apenas {current_qty} unidades (limite: {threshold}). Reposição urgente!",
    )

    logger.warning(
        "notification.stock_low",
        extra={"sku_id": sku_id, "current_qty": current_qty}
    )


async def _send_notification_task(
    notification_id: str,
    recipient_id: str,
    channels: list[str],
    title: str,
    message: str,
):
    """Envia notificação através dos canais especificados."""
    timer = Timer()

    # Buscar preferências do usuário
    prefs_row = await db_pool.fetchrow(
        "SELECT email, phone, push_token FROM notification_preferences WHERE recipient_id = $1",
        recipient_id
    )

    results = {}

    for channel in channels:
        try:
            if channel == "email" and prefs_row and prefs_row["email"]:
                results["email"] = await _send_email(
                    prefs_row["email"],
                    title,
                    message,
                    notification_id
                )
            elif channel == "sms" and prefs_row and prefs_row["phone"]:
                results["sms"] = await _send_sms(
                    prefs_row["phone"],
                    message,
                    notification_id
                )
            elif channel == "push" and prefs_row and prefs_row["push_token"]:
                results["push"] = await _send_push(
                    prefs_row["push_token"],
                    title,
                    message,
                    notification_id
                )
        except Exception as e:
            logger.error(
                f"notification.{channel}_failed",
                extra={
                    "notification_id": notification_id,
                    "recipient_id": recipient_id,
                    "error": str(e)
                }
            )
            results[channel] = False

    # Atualizar status
    success = any(results.values())
    status = "sent" if success else "failed"

    await db_pool.execute(
        "UPDATE notifications SET status = $1, sent_at = NOW() WHERE id = $2",
        status,
        notification_id,
    )

    logger.info(
        "notification.sent",
        extra={
            "notification_id": notification_id,
            "recipient_id": recipient_id,
            "channels": channels,
            "results": results,
            "execution_ms": timer.elapsed_ms,
        }
    )

    for channel, success_flag in results.items():
        NOTIFICATIONS_SENT_TOTAL.labels(
            notification_type="notification",
            channel=channel,
            status="success" if success_flag else "failed"
        ).inc()


async def _send_email(email: str, title: str, message: str, notification_id: str) -> bool:
    """Mock de envio de email."""
    if ENVIRONMENT == "production":
        # TODO: Integrar AWS SES ou SendGrid
        pass
    else:
        # Development: salva em arquivo local
        filename = f"/tmp/notifications/email_{notification_id}.txt"
        try:
            os.makedirs("/tmp/notifications", exist_ok=True)
            async with aiofiles.open(filename, "w") as f:
                await f.write(f"To: {email}\nSubject: {title}\n\n{message}\n")
            logger.info(f"Mock email sent to {email}", extra={"file": filename})
            return True
        except Exception as e:
            logger.error(f"Mock email failed: {e}")
            return False


async def _send_sms(phone: str, message: str, notification_id: str) -> bool:
    """Mock de envio de SMS."""
    if ENVIRONMENT == "production":
        # TODO: Integrar AWS SNS ou Twilio
        pass
    else:
        # Development: log no console
        logger.info(
            "Mock SMS sent",
            extra={
                "to": phone,
                "message": message,
                "notification_id": notification_id
            }
        )
        return True


async def _send_push(push_token: str, title: str, message: str, notification_id: str) -> bool:
    """Mock de envio de push notification."""
    if ENVIRONMENT == "production":
        # TODO: Integrar Firebase Cloud Messaging
        pass
    else:
        # Development: log no console
        logger.info(
            "Mock push sent",
            extra={
                "token": push_token[:20] + "...",
                "title": title,
                "message": message,
                "notification_id": notification_id
            }
        )
        return True
