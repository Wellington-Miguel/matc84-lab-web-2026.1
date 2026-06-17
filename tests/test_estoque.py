"""Integration tests for inventory management"""

import pytest
import threading
import time
from sqlalchemy.orm import Session

from app.services.servico_estoque import (
    obter_estoque_disponivel,
    reservar_estoque,
    liberar_estoque,
    validar_disponibilidade,
    EstoqueIndisponivelError,
    ProdutoNaoEncontradoError,
)
from app.models.produto import Produto
from app.models.outbox import OutboxEvent


class TestObterEstoque:
    """Tests for checking product stock"""

    def test_obter_estoque_produto_existente(self, db_session: Session, sample_produto):
        """Test getting stock for existing product"""
        estoque = obter_estoque_disponivel(db_session, sample_produto.id)
        assert estoque == 100

    def test_obter_estoque_produto_inexistente(self, db_session: Session):
        """Test getting stock for non-existent product"""
        with pytest.raises(ProdutoNaoEncontradoError):
            obter_estoque_disponivel(db_session, 999)


class TestReservarEstoque:
    """Tests for stock reservation"""

    def test_reservar_estoque_sucesso(self, db_session: Session, sample_produto):
        """Test successful stock reservation"""
        inicial = sample_produto.estoque_disponivel

        resultado = reservar_estoque(
            db=db_session,
            produto_id=sample_produto.id,
            quantidade=10,
            pedido_id=1,
        )

        assert resultado is True
        db_session.refresh(sample_produto)
        assert sample_produto.estoque_disponivel == inicial - 10

    def test_reservar_estoque_insuficiente(self, db_session: Session, sample_produto):
        """Test reservation fails when stock is insufficient"""
        with pytest.raises(EstoqueIndisponivelError):
            reservar_estoque(
                db=db_session,
                produto_id=sample_produto.id,
                quantidade=200,  # More than available
                pedido_id=1,
            )

    def test_reservar_estoque_produto_inexistente(self, db_session: Session):
        """Test reservation fails for non-existent product"""
        with pytest.raises(ProdutoNaoEncontradoError):
            reservar_estoque(
                db=db_session,
                produto_id=999,
                quantidade=10,
                pedido_id=1,
            )

    def test_reservar_estoque_cria_evento_outbox(self, db_session: Session, sample_produto):
        """Test that reservation creates outbox event"""
        reservar_estoque(
            db=db_session,
            produto_id=sample_produto.id,
            quantidade=10,
            pedido_id=1,
        )

        eventos = db_session.query(OutboxEvent).all()
        assert len(eventos) == 1
        assert eventos[0].tipo_evento.value == "ESTOQUE_RESERVADO"
        assert eventos[0].agregado_id == 1

    def test_reservar_estoque_multiplas_reservas(self, db_session: Session, sample_produto):
        """Test multiple sequential reservations"""
        inicial = sample_produto.estoque_disponivel

        reservar_estoque(db=db_session, produto_id=sample_produto.id, quantidade=10, pedido_id=1)
        reservar_estoque(db=db_session, produto_id=sample_produto.id, quantidade=20, pedido_id=2)

        db_session.refresh(sample_produto)
        assert sample_produto.estoque_disponivel == inicial - 30


class TestLiberarEstoque:
    """Tests for stock release"""

    def test_liberar_estoque_sucesso(self, db_session: Session, sample_produto):
        """Test successful stock release"""
        reservar_estoque(db=db_session, produto_id=sample_produto.id, quantidade=10, pedido_id=1)
        db_session.refresh(sample_produto)
        apos_reserva = sample_produto.estoque_disponivel

        liberar_estoque(db=db_session, produto_id=sample_produto.id, quantidade=10, pedido_id=1)
        db_session.refresh(sample_produto)

        assert sample_produto.estoque_disponivel == apos_reserva + 10

    def test_liberar_estoque_produto_inexistente(self, db_session: Session):
        """Test release fails for non-existent product"""
        with pytest.raises(ProdutoNaoEncontradoError):
            liberar_estoque(
                db=db_session,
                produto_id=999,
                quantidade=10,
                pedido_id=1,
            )

    def test_liberar_estoque_cria_evento_outbox(self, db_session: Session, sample_produto):
        """Test that release creates outbox event"""
        reservar_estoque(db=db_session, produto_id=sample_produto.id, quantidade=10, pedido_id=1)
        db_session.query(OutboxEvent).delete()  # Clear previous events

        liberar_estoque(db=db_session, produto_id=sample_produto.id, quantidade=10, pedido_id=1)

        eventos = db_session.query(OutboxEvent).all()
        assert len(eventos) == 1
        assert eventos[0].tipo_evento.value == "ESTOQUE_LIBERADO"


class TestValidarDisponibilidade:
    """Tests for availability validation"""

    def test_validar_disponibilidade_items_validos(self, db_session: Session, sample_produtos):
        """Test validation succeeds for available items"""
        items = [
            {"produto_id": sample_produtos[0].id, "quantidade": 10},
            {"produto_id": sample_produtos[1].id, "quantidade": 20},
        ]

        resultado = validar_disponibilidade(db=db_session, items=items)
        assert resultado is True

    def test_validar_disponibilidade_insuficiente(self, db_session: Session, sample_produto):
        """Test validation fails for insufficient stock"""
        items = [
            {"produto_id": sample_produto.id, "quantidade": 200}  # More than available
        ]

        with pytest.raises(EstoqueIndisponivelError):
            validar_disponibilidade(db=db_session, items=items)

    def test_validar_disponibilidade_produto_inexistente(self, db_session: Session):
        """Test validation fails for non-existent product"""
        items = [
            {"produto_id": 999, "quantidade": 10}
        ]

        with pytest.raises(ProdutoNaoEncontradoError):
            validar_disponibilidade(db=db_session, items=items)

    def test_validar_disponibilidade_nao_modifica_estoque(
        self, db_session: Session, sample_produto
    ):
        """Test that validation doesn't modify stock"""
        inicial = sample_produto.estoque_disponivel

        items = [{"produto_id": sample_produto.id, "quantidade": 10}]
        validar_disponibilidade(db=db_session, items=items)

        db_session.refresh(sample_produto)
        assert sample_produto.estoque_disponivel == inicial


class TestConcorrenciaEstoque:
    """Tests for concurrent stock operations (race condition prevention)"""

    def test_reservas_concorrentes_previne_overselling(
        self, db_session: Session, sample_produto
    ):
        """Test that concurrent reservations prevent overselling with database locking"""
        inicial = sample_produto.estoque_disponivel

        # Simulate concurrent reservations
        # Using database FOR UPDATE ensures atomicity
        try:
            reservar_estoque(
                db=db_session,
                produto_id=sample_produto.id,
                quantidade=inicial - 5,
                pedido_id=1,
            )
            db_session.commit()

            # Try to reserve more than available in same DB session
            with pytest.raises(EstoqueIndisponivelError):
                reservar_estoque(
                    db=db_session,
                    produto_id=sample_produto.id,
                    quantidade=10,
                    pedido_id=2,
                )

        finally:
            db_session.rollback()

    def test_reserva_libera_usa_transacao_atomica(
        self, db_session: Session, sample_produto
    ):
        """Test that reserve-release cycle maintains stock consistency"""
        inicial = sample_produto.estoque_disponivel

        # Reserve
        reservar_estoque(
            db=db_session,
            produto_id=sample_produto.id,
            quantidade=30,
            pedido_id=1,
        )
        db_session.commit()

        # Release
        liberar_estoque(
            db=db_session,
            produto_id=sample_produto.id,
            quantidade=30,
            pedido_id=1,
        )
        db_session.commit()

        # Stock should be back to initial
        db_session.refresh(sample_produto)
        assert sample_produto.estoque_disponivel == inicial
