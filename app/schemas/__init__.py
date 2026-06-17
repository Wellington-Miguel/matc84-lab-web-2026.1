"""Pydantic schemas for request/response validation"""

from app.schemas.produto_schema import (
    ProdutoCreate,
    ProdutoRead,
    ProdutoUpdate,
    ProdutoListResponse,
)
from app.schemas.pedido_schema import (
    ItemPedidoCreate,
    ItemPedidoRead,
    PedidoCreate,
    PedidoRead,
    PedidoListResponse,
)

__all__ = [
    "ProdutoCreate",
    "ProdutoRead",
    "ProdutoUpdate",
    "ProdutoListResponse",
    "ItemPedidoCreate",
    "ItemPedidoRead",
    "PedidoCreate",
    "PedidoRead",
    "PedidoListResponse",
]
