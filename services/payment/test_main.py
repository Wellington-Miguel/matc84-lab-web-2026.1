import os
import sys

import pytest
from pydantic import ValidationError
from httpx import AsyncClient, ASGITransport

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from services.payment.main import app, CreatePaymentRequest

@pytest.mark.asyncio
async def test_health_check():
    """Testa se o endpoint de health check responde."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
        # Espera 200 (OK) ou 503 (Degraded) dependendo da conectividade do DB
        assert response.status_code in [200, 503]

def test_payment_rejects_negative_amount():
    """Garante que o modelo CreatePaymentRequest valida que o valor a ser pago seja positivo."""
    with pytest.raises(ValidationError):
        CreatePaymentRequest(order_id="12345", amount=-10.50)
    with pytest.raises(ValidationError):
        CreatePaymentRequest(order_id="12345", amount=0)