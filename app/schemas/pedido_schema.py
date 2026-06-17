from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.models.pedido import StatusPedido


class ItemPedidoCreate(BaseModel):
    """Schema for creating order line items"""
    produto_id: int = Field(..., gt=0)
    quantidade: int = Field(..., gt=0)


class ItemPedidoRead(BaseModel):
    """Schema for reading order line items"""
    id: int
    produto_id: int
    quantidade: int
    preco_unitario: float
    subtotal: float

    class Config:
        from_attributes = True


class PedidoCreate(BaseModel):
    """Schema for creating a new order"""
    cliente_id: int = Field(..., gt=0)
    itens: list[ItemPedidoCreate] = Field(..., min_length=1)

    @field_validator('itens')
    @classmethod
    def validate_items(cls, v: list[ItemPedidoCreate]) -> list[ItemPedidoCreate]:
        """Ensure order has at least one item"""
        if not v or len(v) == 0:
            raise ValueError("Order must have at least one item")
        return v


class PedidoRead(BaseModel):
    """Schema for reading order data"""
    id: int
    cliente_id: int
    status: StatusPedido
    total: float
    total_itens: int
    data_pedido: datetime
    criado_em: datetime
    atualizado_em: datetime
    itens: list[ItemPedidoRead]

    class Config:
        from_attributes = True


class PedidoListResponse(BaseModel):
    """Response schema for order list with pagination"""
    total: int
    pagina: int
    tamanho_pagina: int
    itens: list[PedidoRead]
