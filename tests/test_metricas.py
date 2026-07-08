"""Tests for the Prometheus metrics endpoint and instrumentation.

Uses /health, which the ChaosMiddleware skips, so the metrics recorded are
deterministic and not perturbed by injected latency/failures.
"""

from prometheus_client import CONTENT_TYPE_LATEST


def test_endpoint_metrics_expoe_formato_prometheus(client):
    """/metrics responds in the Prometheus text exposition format."""
    response = client.get("/metrics")

    assert response.status_code == 200
    assert CONTENT_TYPE_LATEST.split(";")[0] in response.headers["content-type"]
    assert "http_request_duration_seconds" in response.text


def test_requisicoes_sao_contabilizadas(client):
    """A handled request increments the traffic counter for its route/status."""
    client.get("/health")

    corpo = client.get("/metrics").text

    # Counter series for the /health route with a 2xx status must be present.
    assert 'http_requests_total{' in corpo
    assert 'path="/health"' in corpo
    assert 'status="200"' in corpo


def test_latencia_observada_para_a_rota(client):
    """The duration histogram records a sample for the exercised route."""
    client.get("/health")

    corpo = client.get("/metrics").text

    assert 'http_request_duration_seconds_count{' in corpo
    assert 'path="/health"' in corpo


def test_rota_inexistente_nao_vaza_cardinalidade(client):
    """404s collapse into a single sentinel label instead of the raw path."""
    from app.core.metricas import ROTA_NAO_ENCONTRADA

    resp = client.get("/rota/que/nao/existe/12345")
    assert resp.status_code == 404

    corpo = client.get("/metrics").text

    assert f'path="{ROTA_NAO_ENCONTRADA}"' in corpo
    # The raw, high-cardinality path must not appear as a label.
    assert "/rota/que/nao/existe/12345" not in corpo


def test_metodo_arbitrario_nao_vaza_cardinalidade(client):
    """Non-standard HTTP verbs collapse into the OTHER sentinel."""
    from app.core.metricas import METODO_OUTRO

    # An arbitrary method token, as a scanner might send.
    client.request("PURGE", "/rota/inexistente")

    corpo = client.get("/metrics").text

    assert f'method="{METODO_OUTRO}"' in corpo
    # The raw verb must never become a label.
    assert 'method="PURGE"' not in corpo
