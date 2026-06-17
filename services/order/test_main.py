import os
import sys

import pytest
from pydantic import ValidationError
from httpx import AsyncClient, ASGITransport

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from services.order.main import app, OrderItem

@pytest.mark.asyncio
async def test_health_check():
    """Testa se o endpoint de health check responde."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
        # Espera 200 (OK) se o DB e Redis do GitHub Actions subirem rápido, ou 503 (Degraded)
        assert response.status_code in [200, 503]


def test_order_item_rejects_negative_unit_price():
    """Garante que o modelo OrderItem valida unit_price positivo."""
    with pytest.raises(ValidationError):
        OrderItem(sku_id="sku-123", quantity=1, unit_price=-5.0)
