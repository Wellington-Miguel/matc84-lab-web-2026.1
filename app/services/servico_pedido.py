"""Order management service"""

import json
from typing import Optional

from sqlalchemy.orm import Session

from app.models.pedido import Pedido, StatusPedido
from app.models.produto import Produto
from app.models.item_pedido import ItemPedido
from app.models.outbox import OutboxEvent, TipoEvento
from app.core.idempotency import (
    get_cached_response,
    store_idempotency_result,
    normalize_idempotency_key,
)
from app.services.servico_estoque import (
    reservar_estoque,
    validar_disponibilidade,
    EstoqueIndisponivelError,
    ProdutoNaoEncontradoError,
)


class PedidoJaExisteError(Exception):
    """Raised when order already exists with same idempotency key"""
    pass


def criar_pedido(
    db: Session,
    cliente_id: int,
    items: list[dict],
    idempotency_key: Optional[str] = None,
) -> dict:
    """
    Create a new order with idempotency support.

    The operation is idempotent: calling with the same idempotency_key
    will return the same result without creating duplicates.

    Args:
        db: Database session
        cliente_id: Customer ID
        items: List of {produto_id, quantidade} dicts
        idempotency_key: Optional idempotency key for request deduplication

    Returns:
        Order response dict with id, status, total, etc.

    Raises:
        EstoqueIndisponivelError: If insufficient stock for any item
        ProdutoNaoEncontradoError: If any product doesn't exist
        ValueError: If items list is empty or invalid
    """
    # Validate inputs
    if not items or len(items) == 0:
        raise ValueError("Order must have at least one item")

    if cliente_id <= 0:
        raise ValueError("cliente_id must be positive")

    normalized_key: Optional[str] = None
    if idempotency_key:
        try:
            normalized_key = normalize_idempotency_key(idempotency_key)
        except ValueError as e:
            raise ValueError(f"Invalid idempotency key: {str(e)}")

        cached = get_cached_response(db, normalized_key)
        if cached:
            return cached

    try:
        # Validate all items are available before creating order
        validar_disponibilidade(db, items)

        # Create order
        pedido = Pedido(
            cliente_id=cliente_id,
            status=StatusPedido.PENDENTE,
        )
        db.add(pedido)
        db.flush()  # Get the order ID without committing

        # Add order items and reserve stock
        total = 0.0
        for item_data in items:
            produto_id = item_data["produto_id"]
            quantidade = item_data["quantidade"]

            reservar_estoque(db, produto_id, quantidade, pedido.id)

            produto = db.query(Produto).filter(Produto.id == produto_id).first()
            if not produto:
                raise ProdutoNaoEncontradoError(f"Produto {produto_id} não encontrado")

            preco_unitario = produto.preco_unitario
            total += quantidade * preco_unitario

            item_pedido = ItemPedido(
                pedido_id=pedido.id,
                produto_id=produto_id,
                quantidade=quantidade,
                preco_unitario=preco_unitario,
            )
            db.add(item_pedido)

        # Update order total
        pedido.total = total
        db.flush()

        # Create outbox event for order creation
        evento = OutboxEvent(
            tipo_evento=TipoEvento.PEDIDO_CRIADO,
            agregado_id=pedido.id,
            dados=json.dumps({
                "pedido_id": pedido.id,
                "cliente_id": cliente_id,
                "total": total,
                "itens_count": len(items),
            }),
        )
        db.add(evento)

        # Commit transaction (includes outbox event)
        db.commit()

        # Build response
        response = {
            "id": pedido.id,
            "cliente_id": pedido.cliente_id,
            "status": pedido.status.value,
            "total": pedido.total,
            "total_itens": len(items),
            "data_pedido": pedido.data_pedido.isoformat(),
        }

        if normalized_key:
            store_idempotency_result(db, normalized_key, response)

        return response

    except Exception:
        db.rollback()
        raise


def obter_pedido(db: Session, pedido_id: int) -> Optional[dict]:
    """
    Get order details by ID.

    Args:
        db: Database session
        pedido_id: The order ID

    Returns:
        Order data dict or None if not found
    """
    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()

    if not pedido:
        return None

    return {
        "id": pedido.id,
        "cliente_id": pedido.cliente_id,
        "status": pedido.status.value,
        "total": pedido.total,
        "total_itens": len(pedido.itens),
        "data_pedido": pedido.data_pedido.isoformat(),
        "criado_em": pedido.criado_em.isoformat(),
        "atualizado_em": pedido.atualizado_em.isoformat(),
        "itens": [
            {
                "id": item.id,
                "produto_id": item.produto_id,
                "quantidade": item.quantidade,
                "preco_unitario": item.preco_unitario,
                "subtotal": item.subtotal,
            }
            for item in pedido.itens
        ],
    }


def listar_pedidos(
    db: Session,
    cliente_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 20,
) -> dict:
    """
    List orders with optional filtering and pagination.

    Args:
        db: Database session
        cliente_id: Optional filter by customer ID
        skip: Number of records to skip
        limit: Maximum records to return

    Returns:
        Dict with total count and list of orders
    """
    query = db.query(Pedido)

    if cliente_id:
        query = query.filter(Pedido.cliente_id == cliente_id)

    total = query.count()
    pedidos = query.offset(skip).limit(limit).all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "pedidos": [
            {
                "id": p.id,
                "cliente_id": p.cliente_id,
                "status": p.status.value,
                "total": p.total,
                "total_itens": len(p.itens),
                "data_pedido": p.data_pedido.isoformat(),
            }
            for p in pedidos
        ],
    }
