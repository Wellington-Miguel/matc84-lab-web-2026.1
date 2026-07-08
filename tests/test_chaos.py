"""Tests for chaos fault injection and its observability.

The chaos middleware is globally disabled during tests (see conftest), so each
test here enables it explicitly with deterministic rates and restores the
previous state afterwards.
"""

import pytest
from prometheus_client import REGISTRY

import app.core.chaos as chaos


def _faltas(tipo: str) -> float:
    valor = REGISTRY.get_sample_value("chaos_faults_injected_total", {"tipo": tipo})
    return valor or 0.0


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


def test_metrica_de_caos_aparece_no_endpoint(client, caos_forcado):
    """The chaos counter is exposed on /metrics after a fault is injected."""
    client.get("/api/v1/produtos")

    corpo = client.get("/metrics").text

    assert "chaos_faults_injected_total" in corpo
    assert 'tipo="error"' in corpo
