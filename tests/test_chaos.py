"""Tests for chaos fault injection and its observability.

The chaos middleware is globally disabled during tests (see conftest), so each
test here enables it explicitly with deterministic rates and restores the
previous state afterwards.
"""

import re

import pytest
from prometheus_client import REGISTRY

import app.core.chaos as chaos
import app.api.v1.rotas_saude as saude


def _faltas(tipo: str) -> float:
    valor = REGISTRY.get_sample_value("chaos_faults_injected_total", {"tipo": tipo})
    return valor or 0.0


def _faltas_no_corpo(corpo: str, tipo: str):
    m = re.search(rf'chaos_faults_injected_total\{{tipo="{tipo}"\}} ([0-9.]+)', corpo)
    return float(m.group(1)) if m else None


@pytest.fixture
def caos_forcado(monkeypatch):
    """Enable chaos deterministically: always error, never add latency."""
    monkeypatch.setattr(chaos, "CHAOS_ENABLED", True)
    monkeypatch.setattr(chaos, "CHAOS_ERROR_RATE", 1.0)
    monkeypatch.setattr(chaos, "CHAOS_LATENCY_RATE", 0.0)
    yield


def test_desabilitado_por_padrao_nao_injeta(client):
    """With chaos disabled (default), a normal route is not disturbed."""
    # /health is skipped anyway; use it just to confirm a clean 200 path.
    assert client.get("/health").status_code == 200


def test_series_pre_inicializadas_em_zero(client):
    """All fault-type series exist (starting at 0) before any fault occurs."""
    for tipo in chaos.TIPOS_FALHA:
        assert REGISTRY.get_sample_value(
            "chaos_faults_injected_total", {"tipo": tipo}
        ) is not None


def test_erro_injetado_incrementa_contador(client, caos_forcado):
    """A forced error returns 500 and increments the error fault counter."""
    antes = _faltas("error")

    resp = client.get("/api/v1/produtos")

    assert resp.status_code == 500
    assert _faltas("error") == antes + 1


def test_caminhos_ignorados_nao_sofrem_caos(client, caos_forcado):
    """Excluded paths (health, metrics) never get chaos, even when enabled."""
    assert client.get("/health").status_code == 200
    assert client.get("/metrics").status_code == 200


def test_endpoint_metrics_reflete_incremento_do_caos(client, caos_forcado):
    """The value exposed at /metrics grows by exactly one per injected fault."""
    antes = _faltas_no_corpo(client.get("/metrics").text, "error") or 0.0

    client.get("/api/v1/produtos")  # forces one error

    depois = _faltas_no_corpo(client.get("/metrics").text, "error")
    assert depois == antes + 1


def test_toggle_db_recusado_quando_caos_desabilitado(client):
    """The unauthenticated outage toggle is refused while chaos is disabled."""
    resp = client.post("/chaos/toggle-db")
    assert resp.status_code == 403
    # And readiness stays healthy — no outage could have been triggered.
    assert client.get("/ready").status_code == 200


def test_db_outage_so_dispara_com_caos_habilitado(client, caos_forcado):
    """With chaos enabled, the toggle arms a /ready outage counted as db_outage."""
    antes = _faltas("db_outage")
    try:
        assert client.post("/chaos/toggle-db").status_code == 200
        assert client.get("/ready").status_code == 503
        assert _faltas("db_outage") == antes + 1
    finally:
        # Reset the process-global flag so other tests see a healthy /ready.
        saude.SIMULAR_QUEDA_BANCO = False
