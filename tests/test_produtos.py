"""Integration tests for product endpoints"""

import pytest
from fastapi.testclient import TestClient

from app.models.produto import Produto


class TestListarProdutos:
    """Tests for GET /api/v1/produtos endpoint"""

    def test_listar_produtos_vazio(self, client: TestClient):
        """Test listing products when database is empty"""
        response = client.get("/api/v1/produtos")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["itens"] == []
        assert data["pagina"] == 1
        assert data["tamanho_pagina"] > 0

    def test_listar_produtos_com_resultados(self, client: TestClient, sample_produtos):
        """Test listing products with multiple items"""
        response = client.get("/api/v1/produtos")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["itens"]) == 3
        assert data["itens"][0]["nome"] == "Cerveja Premium"

    def test_listar_produtos_com_paginacao(self, client: TestClient, sample_produtos):
        """Test pagination parameters"""
        response = client.get("/api/v1/produtos?skip=0&limit=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["itens"]) == 2
        assert data["tamanho_pagina"] == 2

    def test_listar_produtos_com_filtro_categoria(self, client: TestClient, sample_produtos):
        """Test filtering products by category"""
        response = client.get("/api/v1/produtos?categoria=Refrigerante")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["itens"][0]["nome"] == "Refrigerante Cola"

    def test_listar_produtos_limite_maximo(self, client: TestClient, sample_produtos):
        """Test that limit cannot exceed MAX_PAGE_SIZE"""
        response = client.get("/api/v1/produtos?limit=200")
        assert response.status_code == 422  # Validation error


class TestObterProduto:
    """Tests for GET /api/v1/produtos/{id} endpoint"""

    def test_obter_produto_existente(self, client: TestClient, sample_produto):
        """Test getting an existing product"""
        response = client.get(f"/api/v1/produtos/{sample_produto.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_produto.id
        assert data["nome"] == "Cerveja Premium"
        assert data["preco_unitario"] == 15.99
        assert data["estoque_disponivel"] == 100

    def test_obter_produto_inexistente(self, client: TestClient):
        """Test getting a non-existent product"""
        response = client.get("/api/v1/produtos/999")
        assert response.status_code == 404
        assert "não encontrado" in response.json()["detail"].lower()

    def test_obter_produto_id_invalido(self, client: TestClient):
        """Test getting product with invalid ID format"""
        response = client.get("/api/v1/produtos/invalid")
        assert response.status_code == 422  # Validation error

    def test_resposta_contem_timestamps(self, client: TestClient, sample_produto):
        """Test that response includes created and updated timestamps"""
        response = client.get(f"/api/v1/produtos/{sample_produto.id}")
        assert response.status_code == 200
        data = response.json()
        assert "criado_em" in data
        assert "atualizado_em" in data


class TestHealthCheckEndpoints:
    """Tests for health check endpoints"""

    def test_health_endpoint(self, client: TestClient):
        """Test basic health check"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_ready_endpoint_com_db(self, client: TestClient):
        """Test readiness check with database connectivity"""
        response = client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["database"] == "connected"


class TestRootEndpoint:
    """Tests for root endpoint"""

    def test_root_endpoint(self, client: TestClient):
        """Test root endpoint returns API information"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert "version" in data
        assert "status" in data
        assert data["status"] == "running"


class TestValidacao:
    """Tests for data validation in product endpoints"""

    def test_preco_unitario_validacao(self):
        """Test that price validation works"""
        from app.schemas.produto_schema import ProdutoCreate

        # Valid price
        produto = ProdutoCreate(
            nome="Test",
            categoria="Test",
            preco_unitario=10.99,
            estoque_disponivel=5,
        )
        assert produto.preco_unitario == 10.99

        # Invalid price (negative)
        with pytest.raises(ValueError):
            ProdutoCreate(
                nome="Test",
                categoria="Test",
                preco_unitario=-5.99,
                estoque_disponivel=5,
            )

    def test_estoque_validacao(self):
        """Test that stock validation works"""
        from app.schemas.produto_schema import ProdutoCreate

        # Valid stock
        produto = ProdutoCreate(
            nome="Test",
            categoria="Test",
            preco_unitario=10.99,
            estoque_disponivel=100,
        )
        assert produto.estoque_disponivel == 100

        # Invalid stock (negative)
        with pytest.raises(ValueError):
            ProdutoCreate(
                nome="Test",
                categoria="Test",
                preco_unitario=10.99,
                estoque_disponivel=-5,
            )
