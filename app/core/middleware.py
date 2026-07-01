"""Request correlation and access-logging middleware.

Assigns a correlation ID to every request (honoring an inbound
``X-Request-ID`` header when present), binds it to the logging context so all
logs produced while handling the request carry it, echoes it back on the
response, and emits one structured access-log entry per request with the
method, path, status code and latency.
"""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import definir_request_id

REQUEST_ID_HEADER = "X-Request-ID"

logger = logging.getLogger("app.request")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        definir_request_id(request_id)
        request.state.request_id = request_id

        inicio = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duracao_ms = (time.perf_counter() - inicio) * 1000
            logger.exception(
                "request failed",
                extra={
                    "http_method": request.method,
                    "path": request.url.path,
                    "duration_ms": round(duracao_ms, 2),
                },
            )
            definir_request_id(None)
            raise

        duracao_ms = (time.perf_counter() - inicio) * 1000
        response.headers[REQUEST_ID_HEADER] = request_id

        logger.info(
            "request handled",
            extra={
                "http_method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duracao_ms, 2),
            },
        )

        definir_request_id(None)
        return response
