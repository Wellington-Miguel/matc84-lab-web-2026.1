from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.produto import Produto
from app.schemas.produto_schema import ProdutoRead, ProdutoListResponse
from app.core.config import settings

router = APIRouter(prefix="/produtos", tags=["produtos"])


@router.get("", response_model=ProdutoListResponse)
async def listar_produtos(
    skip: int = Query(0, ge=0),
    limit: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    categoria: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> ProdutoListResponse:
    """
    List all products with pagination.

    Query parameters:
    - skip: Number of products to skip (default: 0)
    - limit: Maximum number of products to return (default: 20, max: 100)
    - categoria: Filter by category (optional)
    """
    # Build base query
    query = db.query(Produto)

    # Apply category filter if provided
    if categoria:
        query = query.filter(Produto.categoria == categoria)

    # Get total count
    total = query.count()

    # Apply pagination
    produtos = query.offset(skip).limit(limit).all()

    return ProdutoListResponse(
        total=total,
        pagina=skip // limit + 1 if limit > 0 else 1,
        tamanho_pagina=limit,
        itens=[ProdutoRead.model_validate(p) for p in produtos],
    )


@router.get("/{produto_id}", response_model=ProdutoRead)
async def obter_produto(
    produto_id: int,
    db: Session = Depends(get_db),
) -> ProdutoRead:
    """
    Get a specific product by ID.

    Response time target: < 200ms
    """
    produto = db.query(Produto).filter(Produto.id == produto_id).first()

    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    return ProdutoRead.model_validate(produto)
