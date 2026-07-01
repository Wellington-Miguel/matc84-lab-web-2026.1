"""Structured JSON logging with request correlation support.

Every log record is emitted as a single JSON line and automatically enriched
with the correlation ID of the request being handled (when there is one), so
logs can be traced end-to-end across the request lifecycle.
"""

import contextvars
import datetime as dt
import json
import logging
from typing import Optional

# Holds the correlation ID for the request currently being handled. Using a
# ContextVar keeps it isolated per-request even under async concurrency.
_request_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "request_id", default=None
)


def definir_request_id(request_id: Optional[str]) -> None:
    """Set the correlation ID for the current execution context."""
    _request_id_ctx.set(request_id)


def obter_request_id() -> Optional[str]:
    """Return the correlation ID bound to the current execution context."""
    return _request_id_ctx.get()


class RequestIdFilter(logging.Filter):
    """Injects the current request ID into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = obter_request_id()
        return True


class JSONFormatter(logging.Formatter):
    """Formats log records as compact single-line JSON documents."""

    # Attributes that live on every LogRecord; anything outside this set is
    # treated as caller-provided context and included under the JSON payload.
    _RESERVADOS = {
        "args", "asctime", "created", "exc_info", "exc_text", "filename",
        "funcName", "levelname", "levelno", "lineno", "module", "msecs",
        "message", "msg", "name", "pathname", "process", "processName",
        "relativeCreated", "stack_info", "thread", "threadName", "taskName",
        "request_id",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": dt.datetime.fromtimestamp(
                record.created, tz=dt.timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
        }

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        for chave, valor in record.__dict__.items():
            if chave not in self._RESERVADOS and not chave.startswith("_"):
                payload[chave] = valor

        return json.dumps(payload, default=str, ensure_ascii=False)


def configurar_logging(nivel: str = "INFO") -> None:
    """Configure the root logger to emit structured JSON with request IDs.

    Replaces any handlers previously installed (e.g. by ``basicConfig``) so the
    application has a single, consistent log format.
    """
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(nivel.upper())
