"""Integration tests for order endpoints and services"""

import pytest
import json
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.pedido import Pedido, StatusPedido
from app.services.servico_pedido import criar_pedido, obter_pedido, listar_pedidos
from app.services.servico_estoque import EstoqueIndisponivelError, ProdutoNaoEncontradoError


class TestCriarPedido:
    """Tests for order creation service"""

    def test_criar_pedido_sucesso(self, db_session: Session, sample_produto):
        """Test successful order creation"""
        items = [
            {"produto_id": sample_produto.id, "quantidade": 5}
        ]

        response = criar_pedido(
            db=db_session,
            cliente_id=1,
            items=items,
        )

        assert response["id"] > 0
        assert response["status"] == "PENDENTE"
        assert response["total"] == 5 * 15.99
        assert response["total_itens"] == 1
        assert response["cliente_id"] == 1

    def test_criar_pedido_multiplos_itens(self, db_session: Session, sample_produtos):
        """Test order creation with multiple items"""
        items = [
            {"produto_id": sample_produtos[0].id, "quantidade": 2},
            {"produto_id": sample_produtos[1].id, "quantidade": 3},
        ]

        response = criar_pedido(
            db=db_session,
            cliente_id=1,
            items=items,
        )

        assert response["total_itens"] == 2
        esperado_total = (2 * 15.99) + (3 * 5.99)
        assert abs(response["total"] - esperado_total) < 0.01

    def test_criar_pedido_estoque_insuficiente(self, db_session: Session, sample_produto):
        """Test order creation fails with insufficient stock"""
        items = [
            {"produto_id": sample_produto.id, "quantidade": 200}  # More than available (100)
        ]

        with pytest.raises(EstoqueIndisponivelError):
            criar_pedido(
                db=db_session,
                cliente_id=1,
                items=items,
            )

    def test_criar_pedido_produto_inexistente(self, db_session: Session):
        """Test order creation fails for non-existent product"""
        items = [
            {"produto_id": 999, "quantidade": 5}
        ]

        with pytest.raises(ProdutoNaoEncontradoError):
            criar_pedido(
                db=db_session,
                cliente_id=1,
                items=items,
            )

    def test_criar_pedido_items_vazio(self, db_session: Session):
        """Test order creation fails with empty items"""
        with pytest.raises(ValueError):
            criar_pedido(
                db=db_session,
                cliente_id=1,
                items=[],
            )

    def test_criar_pedido_cliente_invalido(self, db_session: Session, sample_produto):
        """Test order creation fails with invalid client ID"""
        items = [{"produto_id": sample_produto.id, "quantidade": 1}]

        with pytest.raises(ValueError):
            criar_pedido(
                db=db_session,
                cliente_id=-1,
                items=items,
            )

    def test_criar_pedido_estoque_atualizado(self, db_session: Session, sample_produto):
        """Test that stock is reserved after order creation"""
        initial_stock = sample_produto.estoque_disponivel

        items = [{"produto_id": sample_produto.id, "quantidade": 10}]
        criar_pedido(db=db_session, cliente_id=1, items=items)

        # Refresh to get updated stock
        db_session.refresh(sample_produto)
        assert sample_produto.estoque_disponivel == initial_stock - 10


class TestIdempotencia:
    """Tests for idempotent order creation"""

    def test_idempotencia_mesma_chave_retorna_mesmo_resultado(
        self, db_session: Session, sample_produto
    ):
        """Test that same idempotency key returns cached response"""
        items = [{"produto_id": sample_produto.id, "quantidade": 5}]
        chave = "test-key-123"

        response1 = criar_pedido(
            db=db_session,
            cliente_id=1,
            items=items,
            idempotency_key=chave,
        )

        response2 = criar_pedido(
            db=db_session,
            cliente_id=1,
            items=items,
            idempotency_key=chave,
        )

        # Same response returned
        assert response1["id"] == response2["id"]
        assert response1["total"] == response2["total"]

        # Only one order created in database
        pedidos = db_session.query(Pedido).all()
        assert len(pedidos) == 1

    def test_idempotencia_chaves_diferentes_criam_pedidos_diferentes(
        self, db_session: Session, sample_produto
    ):
        """Test that different keys create different orders"""
        items = [{"produto_id": sample_produto.id, "quantidade": 5}]

        response1 = criar_pedido(
            db=db_session,
            cliente_id=1,
            items=items,
            idempotency_key="key-1",
        )

        response2 = criar_pedido(
            db=db_session,
            cliente_id=1,
            items=items,
            idempotency_key="key-2",
        )

        # Different orders created
        assert response1["id"] != response2["id"]

        # Two orders in database
        pedidos = db_session.query(Pedido).all()
        assert len(pedidos) == 2


class TestObterPedido:
    """Tests for retrieving order details"""

    def test_obter_pedido_existente(self, db_session: Session, sample_produto):
        """Test retrieving an existing order"""
        response = criar_pedido(
            db=db_session,
            cliente_id=1,
            items=[{"produto_id": sample_produto.id, "quantidade": 5}],
        )

        pedido = obter_pedido(db=db_session, pedido_id=response["id"])

        assert pedido is not None
        assert pedido["id"] == response["id"]
        assert pedido["cliente_id"] == 1
        assert pedido["status"] == "PENDENTE"
        assert pedido["total_itens"] == 1

    def test_obter_pedido_inexistente(self, db_session: Session):
        """Test retrieving a non-existent order"""
        pedido = obter_pedido(db=db_session, pedido_id=999)
        assert pedido is None

    def test_obter_pedido_contem_itens(self, db_session: Session, sample_produtos):
        """Test that retrieved order contains all items"""
        items = [
            {"produto_id": sample_produtos[0].id, "quantidade": 2},
            {"produto_id": sample_produtos[1].id, "quantidade": 3},
        ]
        response = criar_pedido(db=db_session, cliente_id=1, items=items)

        pedido = obter_pedido(db=db_session, pedido_id=response["id"])

        assert len(pedido["itens"]) == 2
        assert pedido["itens"][0]["quantidade"] == 2
        assert pedido["itens"][1]["quantidade"] == 3


class TestListarPedidos:
    """Tests for listing orders"""

    def test_listar_pedidos_vazio(self, db_session: Session):
        """Test listing when no orders exist"""
        result = listar_pedidos(db=db_session)
        assert result["total"] == 0
        assert len(result["pedidos"]) == 0

    def test_listar_pedidos_multiplos(self, db_session: Session, sample_produto):
        """Test listing multiple orders"""
        # Create multiple orders
        for i in range(3):
            criar_pedido(
                db=db_session,
                cliente_id=i + 1,
                items=[{"produto_id": sample_produto.id, "quantidade": 1}],
            )

        result = listar_pedidos(db=db_session)
        assert result["total"] == 3
        assert len(result["pedidos"]) == 3

    def test_listar_pedidos_filtrar_cliente(self, db_session: Session, sample_produto):
        """Test filtering orders by customer"""
        criar_pedido(
            db=db_session,
            cliente_id=1,
            items=[{"produto_id": sample_produto.id, "quantidade": 1}],
        )
        criar_pedido(
            db=db_session,
            cliente_id=2,
            items=[{"produto_id": sample_produto.id, "quantidade": 1}],
        )

        result = listar_pedidos(db=db_session, cliente_id=1)
        assert result["total"] == 1
        assert result["pedidos"][0]["cliente_id"] == 1

    def test_listar_pedidos_paginacao(self, db_session: Session, sample_produto):
        """Test pagination in order listing"""
        # Create 5 orders
        for i in range(5):
            criar_pedido(
                db=db_session,
                cliente_id=1,
                items=[{"produto_id": sample_produto.id, "quantidade": 1}],
            )

        result = listar_pedidos(db=db_session, skip=0, limit=2)
        assert result["total"] == 5
        assert len(result["pedidos"]) == 2

        result2 = listar_pedidos(db=db_session, skip=2, limit=2)
        assert len(result2["pedidos"]) == 2


class TestCriarPedidoEndpoint:
    """Tests for order creation HTTP endpoint"""

    def test_criar_pedido_endpoint_sucesso(self, client: TestClient, sample_produto):
        """Test successful order creation via HTTP"""
        response = client.post(
            "/api/v1/pedidos",
            json={
                "cliente_id": 1,
                "itens": [
                    {"produto_id": sample_produto.id, "quantidade": 5}
                ],
            },
            headers={"Idempotency-Key": "test-key-1"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] > 0
        assert data["status"] == "PENDENTE"

    def test_criar_pedido_endpoint_estoque_insuficiente(self, client: TestClient, sample_produto):
        """Test order creation fails with 409 for insufficient stock"""
        response = client.post(
            "/api/v1/pedidos",
            json={
                "cliente_id": 1,
                "itens": [
                    {"produto_id": sample_produto.id, "quantidade": 200}
                ],
            },
        )

        assert response.status_code == 409
        assert "Estoque" in response.json()["detail"]

    def test_criar_pedido_endpoint_produto_inexistente(self, client: TestClient):
        """Test order creation fails with 404 for non-existent product"""
        response = client.post(
            "/api/v1/pedidos",
            json={
                "cliente_id": 1,
                "itens": [
                    {"produto_id": 999, "quantidade": 5}
                ],
            },
        )

        assert response.status_code == 404

    def test_criar_pedido_endpoint_items_vazio(self, client: TestClient):
        """Test order creation fails with 400 for empty items"""
        response = client.post(
            "/api/v1/pedidos",
            json={
                "cliente_id": 1,
                "itens": [],
            },
        )

        assert response.status_code == 422  # Validation error

    def test_obter_pedido_endpoint(self, client: TestClient, sample_produto):
        """Test retrieving order via HTTP"""
        # Create order first
        create_response = client.post(
            "/api/v1/pedidos",
            json={
                "cliente_id": 1,
                "itens": [
                    {"produto_id": sample_produto.id, "quantidade": 5}
                ],
            },
        )
        pedido_id = create_response.json()["id"]

        # Get order
        get_response = client.get(f"/api/v1/pedidos/{pedido_id}")
        assert get_response.status_code == 200
        data = get_response.json()
        assert data["id"] == pedido_id
        assert data["cliente_id"] == 1

    def test_listar_pedidos_endpoint(self, client: TestClient, sample_produto):
        """Test listing orders via HTTP"""
        # Create 3 orders
        for i in range(3):
            client.post(
                "/api/v1/pedidos",
                json={
                    "cliente_id": 1,
                    "itens": [
                        {"produto_id": sample_produto.id, "quantidade": 1}
                    ],
                },
            )

        response = client.get("/api/v1/pedidos")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
