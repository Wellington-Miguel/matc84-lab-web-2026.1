"""Métricas Prometheus para os sinais dourados (latência, tráfego, erros).

Expõe um middleware que cronometra cada requisição HTTP e registra sua duração
e resultado, além de uma função para renderizar as métricas no formato de texto
do Prometheus (consumido pelo endpoint ``/metrics``).

As métricas de negócio, fila outbox e caos vivem em outros módulos, mas
compartilham o mesmo registry padrão do ``prometheus_client``.
"""

import time

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Tráfego + Erros: total de requisições rotuladas por método, rota e status.
# A taxa de 5xx sobre o total é o SLI de disponibilidade (SLO >= 99,5%).
http_requests_total = Counter(
    "http_requests_total",
    "Total de requisições HTTP processadas.",
    ["method", "path", "status"],
)

# Latência: histograma da duração das requisições em segundos. Os buckets são
# escolhidos em torno do SLO de latência da API (p95 < 500ms) para dar
# resolução útil na faixa que importa.
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "Duração das requisições HTTP em segundos.",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)


# Sentinel label for requests that matched no route (e.g. 404s). Using the raw
# URL path here would let scanners hitting random URLs blow up the metric
# cardinality, so all unmatched paths collapse into a single series.
ROTA_NAO_ENCONTRADA = "__unmatched__"

# The ASGI layer accepts an arbitrary token as the HTTP method, so labelling
# with the raw method is an open cardinality vector (a scanner sending random
# verbs like PURGE/FOOBAR would create unbounded {method=...} series). We map
# anything outside the standard set to a single sentinel.
METODOS_CONHECIDOS = frozenset(
    {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE", "CONNECT"}
)
METODO_OUTRO = "OTHER"


def _rotulo_metodo(metodo: str) -> str:
    """Collapse non-standard HTTP methods into a sentinel to bound cardinality."""
    return metodo if metodo in METODOS_CONHECIDOS else METODO_OUTRO


def _rotulo_rota(request: Request) -> str:
    """Return the matched route template to keep label cardinality bounded.

    Using the raw URL path would explode cardinality (``/pedidos/1``,
    ``/pedidos/2``, ...). The route template (``/pedidos/{pedido_id}``) groups
    them. Unmatched paths collapse into a single sentinel series.
    """
    rota = request.scope.get("route")
    caminho = getattr(rota, "path", None)
    return caminho or ROTA_NAO_ENCONTRADA


class MetricsMiddleware(BaseHTTPMiddleware):
    """Records duration and outcome of every request.

    Placed as the outermost middleware so it observes the client-visible
    latency and status — including any latency or 5xx injected by the chaos
    middleware downstream.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        inicio = time.perf_counter()
        status = 500  # assume failure until proven otherwise (unhandled exception)
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            duracao = time.perf_counter() - inicio
            caminho = _rotulo_rota(request)
            metodo = _rotulo_metodo(request.method)
            http_request_duration_seconds.labels(metodo, caminho).observe(duracao)
            http_requests_total.labels(metodo, caminho, str(status)).inc()


def gerar_metricas() -> Response:
    """Render the current metrics in the Prometheus text exposition format."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
