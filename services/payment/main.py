"""
services/payment/main.py
Payment Service — microsserviço de pagamentos com:
  - Idempotência obrigatória (evita cobrança dupla)
  - Logs estruturados JSON
  - Health check para ALB
"""
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

import asyncpg
from fastapi import FastAPI, Request, Header, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

# Imports compartilhados (ajuste o PYTHONPATH ao rodar)
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

from shared.logger import get_logger, LogContext, Timer
from shared.idempotency import IdempotencyGuard

logger = get_logger("payment-service")

# ── Configurações (via variáveis de ambiente) ─────────────────────────────────
DB_URL = os.getenv("DATABASE_URL", "postgresql://bebidasadmin:senha@localhost/bebidas")

# ── Recursos globais ──────────────────────────────────────────────────────────
db_pool: asyncpg.Pool = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa e encerra conexões ao subir/derrubar o serviço."""
    global db_pool

    logger.info("payment-service.starting")
    db_pool = await asyncpg.create_pool(DB_URL, min_size=5, max_size=20)
    logger.info("payment-service.ready")
    
    yield  # aplicação rodando

    await db_pool.close()
    logger.info("payment-service.shutdown")

app = FastAPI(title="Payment Service", lifespan=lifespan)

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
class CreatePaymentRequest(BaseModel):
    order_id: str
    amount: float
    provider_ref: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v):
        if v <= 0:
            raise ValueError("Amount deve ser um valor positivo")
        return v

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

    all_ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={"status": "healthy" if all_ok else "degraded", "checks": checks}
    )

@app.post("/payments", status_code=status.HTTP_201_CREATED)
async def create_payment(
    payload: CreatePaymentRequest,
    idempotency_key: Optional[str] = Header(None, alias="idempotency-key"),
):
    """
    Processa um pagamento com garantia de execução única.
    """
    timer = Timer()
    
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Header idempotency-key é obrigatório"
        )
    key = IdempotencyGuard.validate_key(idempotency_key)

    guard = IdempotencyGuard(db_pool)

    try:
        payment = await guard.execute(
            key=key,
            operation=lambda conn: _persist_payment(conn, payload, key),
        )
    except Exception as err:
        logger.error("payment.create_failed",
                    extra={
                        "error_type": type(err).__name__,
                        "execution_ms": timer.elapsed_ms,
                        "status": "error",
                    },
                )
        raise HTTPException(status_code=500, detail="Erro interno ao processar pagamento")

    logger.info("payment.created",
                extra={
                    "payment_id": payment["id"],
                    "order_id": payload.order_id,
                    "amount": payload.amount,
                    "execution_ms": timer.elapsed_ms,
                    "status": "success",
                })
    return payment

# ── Funções internas ──────────────────────────────────────────────────────────

async def _persist_payment(conn: asyncpg.Connection, payload: CreatePaymentRequest, idempotency_key: str) -> dict:
    payment_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    await conn.execute(
        """
        INSERT INTO payments (id, order_id, amount, status, provider_ref, idempotency_key, created_at)
        VALUES ($1, $2, $3, 'completed', $4, $5, $6)
        """,
        payment_id, payload.order_id, payload.amount, payload.provider_ref, idempotency_key, now
    )

    # Retorna o dicionário representando o pagamento inserido
    return {
        "id": payment_id, "order_id": payload.order_id, "amount": payload.amount,
        "status": "completed", "provider_ref": payload.provider_ref, "created_at": now.isoformat()
    }