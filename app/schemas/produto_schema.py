from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProdutoBase(BaseModel):
    """Base schema for product data"""
    nome: str = Field(..., min_length=1, max_length=255)
    descricao: Optional[str] = Field(None, max_length=1024)
    categoria: str = Field(..., min_length=1, max_length=100)
    preco_unitario: float = Field(..., gt=0)
    estoque_disponivel: int = Field(default=0, ge=0)

    @field_validator("preco_unitario")
    @classmethod
    def arredondar_preco(cls, v: float) -> float:
        return round(v, 2)


class ProdutoCreate(ProdutoBase):
    """Schema for creating a new product"""
    pass


class ProdutoUpdate(BaseModel):
    """Schema for updating a product"""
    nome: Optional[str] = Field(None, min_length=1, max_length=255)
    descricao: Optional[str] = Field(None, max_length=1024)
    categoria: Optional[str] = Field(None, min_length=1, max_length=100)
    preco_unitario: Optional[float] = Field(None, gt=0)
    estoque_disponivel: Optional[int] = Field(None, ge=0)


class ProdutoRead(ProdutoBase):
    """Schema for reading product data"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    criado_em: datetime
    atualizado_em: datetime


class ProdutoListResponse(BaseModel):
    """Response schema for product list with pagination"""
    total: int
    pagina: int
    tamanho_pagina: int
    itens: list[ProdutoRead]


class RelatorioBaixoEstoqueResponse(BaseModel):
    """Response schema for the low-stock report.

    Lists every product whose available stock is at or below ``limite``,
    ordered from the most critical (lowest stock) to the least critical.
    """
    limite: int
    total: int
    itens: list[ProdutoRead]
