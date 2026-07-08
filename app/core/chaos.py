"""Chaos Engineering middleware: injects latency and errors on demand.

Fault injection is DISABLED by default (see ``CHAOS_ENABLED``) and only turned
on explicitly — via ``CHAOS_ENABLED=true`` in the environment — for resilience
experiments, so it can never degrade a real deployment by accident.

Every injected fault is counted in ``chaos_faults_injected_total`` so the blast
radius of an experiment is observable: dashboards can show how much chaos is
being injected, and error-budget analysis can separate injected failures from
organic ones.
"""

import asyncio
import random

from fastapi import Request, Response
from prometheus_client import Counter
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings

# Sourced from settings (env-driven). Kept as module-level names so tests (and
# the /chaos endpoints) can flip them at runtime without re-reading the env.
CHAOS_ENABLED = settings.CHAOS_ENABLED
CHAOS_ERROR_RATE = settings.CHAOS_ERROR_RATE
CHAOS_LATENCY_RATE = settings.CHAOS_LATENCY_RATE
CHAOS_MIN_LATENCY = settings.CHAOS_MIN_LATENCY
CHAOS_MAX_LATENCY = settings.CHAOS_MAX_LATENCY

# Paths never subjected to chaos, so health checks, metrics scraping and docs
# stay reliable while an experiment runs.
CAMINHOS_IGNORADOS = ("/", "/health", "/ready", "/metrics", "/docs", "/openapi.json")

# Observability of the chaos itself, labelled by fault type
# (``latency`` | ``error`` | ``db_outage``).
chaos_faults_injected_total = Counter(
    "chaos_faults_injected_total",
    "Total de falhas injetadas pelo Chaos Engineering, por tipo.",
    ["tipo"],
)


class ChaosMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not CHAOS_ENABLED:
            return await call_next(request)

        if request.url.path in CAMINHOS_IGNORADOS or "/chaos" in request.url.path:
            return await call_next(request)

        if random.random() < CHAOS_LATENCY_RATE:
            latency = random.uniform(CHAOS_MIN_LATENCY, CHAOS_MAX_LATENCY)
            chaos_faults_injected_total.labels("latency").inc()
            await asyncio.sleep(latency)

        if random.random() < CHAOS_ERROR_RATE:
            chaos_faults_injected_total.labels("error").inc()
            return Response(
                content="💥 Chaos Engineering: Falha simulada pelo Middleware do Caos!",
                status_code=500,
            )

        return await call_next(request)
