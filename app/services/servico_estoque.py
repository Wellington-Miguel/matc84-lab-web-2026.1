"""Inventory management service"""

import json

from sqlalchemy.orm import Session

from app.models.produto import Produto
from app.models.outbox import OutboxEvent, TipoEvento


class EstoqueIndisponivelError(Exception):
    """Raised when insufficient stock is available"""
    pass


class ProdutoNaoEncontradoError(Exception):
    """Raised when product is not found"""
    pass


def obter_estoque_disponivel(db: Session, produto_id: int) -> int:
    """
    Get current available stock for a product.

    Args:
        db: Database session
        produto_id: The product ID

    Returns:
        The available stock quantity

    Raises:
        ProdutoNaoEncontradoError: If product doesn't exist
    """
    produto = db.query(Produto).filter(Produto.id == produto_id).first()

    if not produto:
        raise ProdutoNaoEncontradoError(f"Produto {produto_id} não encontrado")

    return produto.estoque_disponivel


def reservar_estoque(
    db: Session,
    produto_id: int,
    quantidade: int,
    pedido_id: int,
) -> bool:
    """
    Reserve stock for an order atomically using database-level locking.

    This function uses SELECT FOR UPDATE to prevent race conditions.

    Args:
        db: Database session
        produto_id: The product ID to reserve
        quantidade: The quantity to reserve
        pedido_id: The order ID requesting the reservation

    Returns:
        True if reservation succeeded

    Raises:
        ProdutoNaoEncontradoError: If product doesn't exist
        EstoqueIndisponivelError: If insufficient stock available
    """
    # Use SELECT FOR UPDATE to lock the row and prevent race conditions
    produto = db.query(Produto).with_for_update().filter(
        Produto.id == produto_id
    ).first()

    if not produto:
        raise ProdutoNaoEncontradoError(f"Produto {produto_id} não encontrado")

    if produto.estoque_disponivel < quantidade:
        raise EstoqueIndisponivelError(
            f"Estoque insuficiente para produto {produto_id}. "
            f"Disponível: {produto.estoque_disponivel}, Solicitado: {quantidade}"
        )

    produto.estoque_disponivel -= quantidade

    evento = OutboxEvent(
        tipo_evento=TipoEvento.ESTOQUE_RESERVADO,
        agregado_id=pedido_id,
        dados=json.dumps({
            "produto_id": produto_id,
            "quantidade": quantidade,
            "pedido_id": pedido_id,
        }),
    )
    db.add(evento)
    db.flush()

    return True


def liberar_estoque(
    db: Session,
    produto_id: int,
    quantidade: int,
    pedido_id: int,
) -> bool:
    """
    Release reserved stock if an order fails.

    Args:
        db: Database session
        produto_id: The product ID to release
        quantidade: The quantity to release
        pedido_id: The order ID

    Returns:
        True if release succeeded

    Raises:
        ProdutoNaoEncontradoError: If product doesn't exist
    """
    # Use SELECT FOR UPDATE to lock the row
    produto = db.query(Produto).with_for_update().filter(
        Produto.id == produto_id
    ).first()

    if not produto:
        raise ProdutoNaoEncontradoError(f"Produto {produto_id} não encontrado")

    produto.estoque_disponivel += quantidade

    evento = OutboxEvent(
        tipo_evento=TipoEvento.ESTOQUE_LIBERADO,
        agregado_id=pedido_id,
        dados=json.dumps({
            "produto_id": produto_id,
            "quantidade": quantidade,
            "pedido_id": pedido_id,
        }),
    )
    db.add(evento)
    db.flush()

    return True


def validar_disponibilidade(
    db: Session,
    items: list[dict],
) -> bool:
    """
    Validate that all items have sufficient stock without reserving.

    Used to check availability before creating order.

    Args:
        db: Database session
        items: List of {produto_id, quantidade} dicts

    Returns:
        True if all items have sufficient stock

    Raises:
        EstoqueIndisponivelError: If any item has insufficient stock
    """
    for item in items:
        produto_id = item["produto_id"]
        quantidade = item["quantidade"]

        disponivel = obter_estoque_disponivel(db, produto_id)
        if disponivel < quantidade:
            raise EstoqueIndisponivelError(
                f"Estoque insuficiente para produto {produto_id}. "
                f"Disponível: {disponivel}, Solicitado: {quantidade}"
            )

    return True
