from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ProdutoBase(BaseModel):
    """Base schema for product data"""
    nome: str = Field(..., min_length=1, max_length=255)
    descricao: Optional[str] = Field(None, max_length=1024)
    categoria: str = Field(..., min_length=1, max_length=100)
    preco_unitario: float = Field(..., gt=0)
    estoque_disponivel: int = Field(default=0, ge=0)

    @field_validator('preco_unitario')
    @classmethod
    def validate_price(cls, v: float) -> float:
        """Ensure price is positive and has max 2 decimal places"""
        if v <= 0:
            raise ValueError("Price must be greater than 0")
        return round(v, 2)

    @field_validator('estoque_disponivel')
    @classmethod
    def validate_stock(cls, v: int) -> int:
        """Ensure stock is non-negative"""
        if v < 0:
            raise ValueError("Stock cannot be negative")
        return v


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
    id: int
    criado_em: datetime
    atualizado_em: datetime

    class Config:
        from_attributes = True


class ProdutoListResponse(BaseModel):
    """Response schema for product list with pagination"""
    total: int
    pagina: int
    tamanho_pagina: int
    itens: list[ProdutoRead]
