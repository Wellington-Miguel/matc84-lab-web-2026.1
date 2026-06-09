import pytest
from httpx import AsyncClient, ASGITransport
from services.order.main import app

@pytest.mark.asyncio
async def test_health_check():
    """Testa se o endpoint de health check responde."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
        # Espera 200 (OK) se o DB e Redis do GitHub Actions subirem rápido, ou 503 (Degraded)
        assert response.status_code in [200, 503]