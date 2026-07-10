from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.produto import Produto
from app.schemas.produto_schema import (
    ProdutoRead,
    ProdutoListResponse,
    RelatorioBaixoEstoqueResponse,
)
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


@router.get("/baixo-estoque", response_model=RelatorioBaixoEstoqueResponse)
async def relatorio_baixo_estoque(
    limite: int = Query(
        settings.LIMITE_ESTOQUE_BAIXO_PADRAO,
        ge=0,
        description="Considera em baixo estoque todo produto com estoque <= limite.",
    ),
    db: Session = Depends(get_db),
) -> RelatorioBaixoEstoqueResponse:
    """
    Low-stock report.

    Returns every product whose available stock is at or below `limite`,
    sorted ascending by stock (most critical first). Intended as a simple
    read-only alert for restocking decisions — it does not reserve, alter,
    or lock any inventory, it only reports the current snapshot.

    Note: this route is declared before `/{produto_id}` so that
    "/produtos/baixo-estoque" is matched here instead of being interpreted
    as a (non-numeric) product id.
    """
    produtos = (
        db.query(Produto)
        .filter(Produto.estoque_disponivel <= limite)
        .order_by(Produto.estoque_disponivel.asc())
        .all()
    )

    return RelatorioBaixoEstoqueResponse(
        limite=limite,
        total=len(produtos),
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
