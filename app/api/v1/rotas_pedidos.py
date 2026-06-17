"""Order management API endpoints"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.pedido_schema import PedidoCreate, PedidoRead, PedidoListResponse
from app.services.servico_pedido import (
    criar_pedido,
    obter_pedido,
    listar_pedidos,
)
from app.services.servico_estoque import (
    EstoqueIndisponivelError,
    ProdutoNaoEncontradoError,
)

router = APIRouter(prefix="/pedidos", tags=["pedidos"])


@router.post("", response_model=dict)
async def criar_novo_pedido(
    pedido_request: PedidoCreate,
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(None),
) -> dict:
    """
    Create a new order.

    This endpoint is idempotent: providing the same Idempotency-Key header
    will return the same result without creating duplicate orders.

    Request body:
    - cliente_id: Customer ID (required, > 0)
    - itens: List of items with produto_id and quantidade (required, min 1 item)

    Headers:
    - Idempotency-Key: Optional key for request deduplication

    Returns:
    - id: Order ID
    - status: Order status (PENDENTE)
    - total: Order total value
    - total_itens: Number of items

    Error codes:
    - 400: Invalid request (invalid client ID, empty items, etc.)
    - 404: Product not found
    - 409: Insufficient stock available
    """
    try:
        # Convert request items to dict format for service
        items = [
            {
                "produto_id": item.produto_id,
                "quantidade": item.quantidade,
            }
            for item in pedido_request.itens
        ]

        response = criar_pedido(
            db=db,
            cliente_id=pedido_request.cliente_id,
            items=items,
            idempotency_key=idempotency_key,
        )

        return response

    except EstoqueIndisponivelError as e:
        raise HTTPException(
            status_code=409,
            detail=f"Estoque indisponível: {str(e)}",
        )
    except ProdutoNaoEncontradoError as e:
        raise HTTPException(
            status_code=404,
            detail=f"Produto não encontrado: {str(e)}",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Requisição inválida: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao criar pedido: {str(e)}",
        )


@router.get("/{pedido_id}", response_model=dict)
async def obter_detalhes_pedido(
    pedido_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """
    Get order details by ID.

    Returns:
    - id, cliente_id, status, total
    - total_itens: Number of items
    - itens: List of order items with produto_id, quantidade, preco_unitario, subtotal
    - data_pedido, criado_em, atualizado_em: Timestamps

    Response time target: < 200ms
    """
    pedido = obter_pedido(db, pedido_id)

    if not pedido:
        raise HTTPException(
            status_code=404,
            detail="Pedido não encontrado",
        )

    return pedido


@router.get("", response_model=dict)
async def listar_pedidos_cliente(
    cliente_id: Optional[int] = Query(None, gt=0),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    """
    List orders with pagination and optional filtering.

    Query parameters:
    - cliente_id: Filter by customer ID (optional)
    - skip: Number of orders to skip (default: 0)
    - limit: Maximum number of orders to return (default: 20, max: 100)

    Returns:
    - total: Total number of orders matching filter
    - skip, limit: Pagination parameters
    - pedidos: List of order summaries
    """
    result = listar_pedidos(
        db=db,
        cliente_id=cliente_id,
        skip=skip,
        limit=limit,
    )

    return {
        "total": result["total"],
        "pagina": skip // limit + 1 if limit > 0 else 1,
        "tamanho_pagina": limit,
        "itens": result["pedidos"],
    }
