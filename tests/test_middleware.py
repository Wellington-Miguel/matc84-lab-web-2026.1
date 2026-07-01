"""Tests for the request-correlation middleware.

Uses the /health endpoint, which the ChaosMiddleware skips, so responses are
deterministic and not subject to injected latency/failures.
"""

import uuid

from app.core.middleware import REQUEST_ID_HEADER


def test_gera_request_id_quando_ausente(client):
    """A correlation ID is generated and returned when none is provided."""
    response = client.get("/health")

    assert response.status_code == 200
    request_id = response.headers.get(REQUEST_ID_HEADER)
    assert request_id is not None
    # Generated IDs are valid UUIDs.
    uuid.UUID(request_id)


def test_propaga_request_id_fornecido(client):
    """An inbound X-Request-ID is echoed back unchanged on the response."""
    fornecido = "req-teste-12345"

    response = client.get("/health", headers={REQUEST_ID_HEADER: fornecido})

    assert response.status_code == 200
    assert response.headers.get(REQUEST_ID_HEADER) == fornecido


def test_request_ids_sao_unicos_por_requisicao(client):
    """Distinct requests without an inbound ID get distinct correlation IDs."""
    primeiro = client.get("/health").headers.get(REQUEST_ID_HEADER)
    segundo = client.get("/health").headers.get(REQUEST_ID_HEADER)

    assert primeiro != segundo
