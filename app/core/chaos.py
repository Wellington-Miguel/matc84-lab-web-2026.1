import asyncio
import random
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

CHAOS_ENABLED = True
CHAOS_ERROR_RATE = 0.2
CHAOS_LATENCY_RATE = 0.3
CHAOS_MIN_LATENCY = 1.0
CHAOS_MAX_LATENCY = 3.0

class ChaosMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not CHAOS_ENABLED:
            return await call_next(request)

        if request.url.path in ["/", "/health", "/ready", "/docs", "/openapi.json"] or "/chaos" in request.url.path:
            return await call_next(request)

        if random.random() < CHAOS_LATENCY_RATE:
            latency = random.uniform(CHAOS_MIN_LATENCY, CHAOS_MAX_LATENCY)
            await asyncio.sleep(latency)

        if random.random() < CHAOS_ERROR_RATE:
            return Response(
                content="💥 Chaos Engineering: Falha simulada pelo Middleware do Caos!",
                status_code=500
            )

        return await call_next(request)