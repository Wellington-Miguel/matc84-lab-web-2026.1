from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.pedido import StatusPedido


class ItemPedidoCreate(BaseModel):
    """Schema for creating order line items"""
    produto_id: int = Field(..., gt=0)
    quantidade: int = Field(..., gt=0)


class ItemPedidoRead(BaseModel):
    """Schema for reading order line items"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    produto_id: int
    quantidade: int
    preco_unitario: float
    subtotal: float


class PedidoCreate(BaseModel):
    """Schema for creating a new order"""
    cliente_id: int = Field(..., gt=0)
    itens: list[ItemPedidoCreate] = Field(..., min_length=1)


class PedidoRead(BaseModel):
    """Schema for reading order data"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    cliente_id: int
    status: StatusPedido
    total: float
    total_itens: int
    data_pedido: datetime
    criado_em: datetime
    atualizado_em: datetime
    itens: list[ItemPedidoRead]


class PedidoListResponse(BaseModel):
    """Response schema for order list with pagination"""
    total: int
    pagina: int
    tamanho_pagina: int
    itens: list[PedidoRead]
