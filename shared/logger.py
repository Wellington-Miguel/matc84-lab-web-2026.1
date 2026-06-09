"""
shared/logger.py
Logger estruturado em JSON — obrigatório conforme o plano estratégico.

Campos obrigatórios em todo log:
  - timestamp, request_id, correlation_id, status, execution_ms, error_type

Uso:
    from shared.logger import get_logger, LogContext

    logger = get_logger("order-service")

    with LogContext(correlation_id="uuid-aqui", request_id="req-123"):
        logger.info("order.created", order_id="abc", total=99.90)
"""
import json
import logging
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Optional

# Variáveis de contexto — propagam pelo request sem passar manualmente
_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")
_request_id: ContextVar[str] = ContextVar("request_id", default="")


class JsonFormatter(logging.Formatter):
    """Formata todos os logs como JSON de uma linha (para CloudWatch)."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": record.name,
            "message": record.getMessage(),
            "request_id": _request_id.get() or record.__dict__.get("request_id", ""),
            "correlation_id": _correlation_id.get() or record.__dict__.get("correlation_id", ""),
            "status": record.__dict__.get("status", ""),
            "execution_ms": record.__dict__.get("execution_ms", None),
            "error_type": record.__dict__.get("error_type", None),
        }

        # Adiciona campos extras passados via `extra={...}`
        for key, val in record.__dict__.items():
            if key not in ("message", "msg", "args", "levelname", "levelno",
                           "name", "pathname", "filename", "module", "exc_info",
                           "exc_text", "stack_info", "lineno", "funcName",
                           "created", "msecs", "relativeCreated", "thread",
                           "threadName", "processName", "process", "taskName"):
                if key not in log_entry:
                    log_entry[key] = val

        # Remove nulos para manter logs limpos
        log_entry = {k: v for k, v in log_entry.items() if v is not None and v != ""}

        return json.dumps(log_entry, ensure_ascii=False, default=str)


def get_logger(service_name: str) -> logging.Logger:
    """Retorna logger configurado com formatter JSON."""
    logger = logging.getLogger(service_name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


class LogContext:
    """
    Context manager que injeta correlation_id e request_id no contexto.

    Uso em FastAPI:
        @app.middleware("http")
        async def correlation_middleware(request: Request, call_next):
            correlation_id = request.headers.get("x-correlation-id") or str(uuid.uuid4())
            request_id = str(uuid.uuid4())
            with LogContext(correlation_id=correlation_id, request_id=request_id):
                response = await call_next(request)
                response.headers["x-correlation-id"] = correlation_id
                return response
    """

    def __init__(self, correlation_id: Optional[str] = None, request_id: Optional[str] = None):
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.request_id = request_id or str(uuid.uuid4())
        self._tokens = []

    def __enter__(self):
        self._tokens.append(_correlation_id.set(self.correlation_id))
        self._tokens.append(_request_id.set(self.request_id))
        return self

    def __exit__(self, *_):
        for token in self._tokens:
            token.var.reset(token)


class Timer:
    """Cronômetro simples para medir execution_ms."""

    def __init__(self):
        self._start = time.monotonic()

    @property
    def elapsed_ms(self) -> int:
        return round((time.monotonic() - self._start) * 1000)
