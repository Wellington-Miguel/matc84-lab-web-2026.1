"""
services/catalog/main.py
Catalog Service — microsserviço de catálogo com:
  - CRUD de produtos e categorias
  - Cache Redis inteligente (TTL: 1 hora)
  - Busca avançada (nome, categoria, preço)
  - Validação com Pydantic
  - Soft delete (active flag)
  - Métricas Prometheus
  - Health check para ALB
"""
import os
import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional, List

import asyncpg
import redis.asyncio as aioredis
from fastapi import FastAPI, Request, Response, HTTPException, status, Query
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, Gauge, generate_latest
from pydantic import BaseModel, field_validator

# Imports compartilhados
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

from shared.logger import get_logger, LogContext, Timer

logger = get_logger("catalog-service")

# ── Métricas Prometheus ────────────────────────────────────────────────────────
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total de requisicoes HTTP",
    ["method", "path", "status"],
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "Duracao das requisicoes HTTP",
    ["method", "path"],
)
PRODUCTS_TOTAL = Gauge(
    "catalog_products_total",
    "Total de produtos ativos no catálogo",
)
CACHE_HITS = Counter(
    "cache_hits_total",
    "Total de cache hits por tipo",
    ["resource_type"],
)
CACHE_MISSES = Counter(
    "cache_misses_total",
    "Total de cache misses por tipo",
    ["resource_type"],
)
PRODUCTS_CREATED = Counter(
    "products_created_total",
    "Total de produtos criados",
)
PRODUCTS_UPDATED = Counter(
    "products_updated_total",
    "Total de produtos atualizados",
)
PRODUCTS_DELETED = Counter(
    "products_deleted_total",
    "Total de produtos deletados",
)

# ── Configurações ──────────────────────────────────────────────────────────────
DB_URL    = os.getenv("DATABASE_URL", "postgresql://bebidasadmin:senha_local_dev@localhost/bebidas")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
CACHE_TTL = 3600  # 1 hora

# ── Recursos globais ──────────────────────────────────────────────────────────
db_pool: asyncpg.Pool = None
redis_client: aioredis.Redis = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa e encerra conexões."""
    global db_pool, redis_client

    logger.info("catalog-service.starting")

    db_pool = await asyncpg.create_pool(DB_URL, min_size=5, max_size=20)
    redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)

    # Atualizar gauge de produtos ativos
    active_products = await db_pool.fetchval(
        "SELECT COUNT(*) FROM products WHERE active = true"
    )
    PRODUCTS_TOTAL.set(active_products or 0)

    logger.info("catalog-service.ready")
    yield  # aplicação rodando

    await db_pool.close()
    await redis_client.close()
    logger.info("catalog-service.shutdown")


app = FastAPI(title="Catalog Service", lifespan=lifespan)


# ── Middleware: Correlation ID ─────────────────────────────────────────────────
@app.middleware("http")
async def correlation_middleware(request: Request, call_next):
    correlation_id = request.headers.get("x-correlation-id") or str(uuid.uuid4())
    request_id = str(uuid.uuid4())
    timer = Timer()
    status_code = 500

    with LogContext(correlation_id=correlation_id, request_id=request_id):
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["x-correlation-id"] = correlation_id
            return response
        finally:
            path = _route_template(request)
            if path != "/metrics":
                HTTP_REQUESTS_TOTAL.labels(
                    method=request.method,
                    path=path,
                    status=str(status_code),
                ).inc()
                HTTP_REQUEST_DURATION_SECONDS.labels(
                    method=request.method,
                    path=path,
                ).observe(timer.elapsed_ms / 1000)


# ── Models ─────────────────────────────────────────────────────────────────────

class CategoryResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    created_at: str


class ProductResponse(BaseModel):
    id: str
    sku: str
    name: str
    description: Optional[str] = None
    price: float
    category_id: Optional[str] = None
    category_name: Optional[str] = None
    active: bool
    created_at: str
    updated_at: str


class CreateProductRequest(BaseModel):
    sku: str
    name: str
    description: Optional[str] = None
    price: float
    category_id: Optional[str] = None

    @field_validator("sku")
    @classmethod
    def validate_sku(cls, v):
        if not v or len(v) < 3:
            raise ValueError("SKU deve ter pelo menos 3 caracteres")
        return v.upper()

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if not v or len(v) < 3:
            raise ValueError("Nome deve ter pelo menos 3 caracteres")
        return v

    @field_validator("price")
    @classmethod
    def validate_price(cls, v):
        if v <= 0:
            raise ValueError("Preço deve ser positivo")
        return round(v, 2)


class UpdateProductRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    category_id: Optional[str] = None
    active: Optional[bool] = None

    @field_validator("price")
    @classmethod
    def validate_price(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Preço deve ser positivo")
        return round(v, 2) if v else None


class CreateCategoryRequest(BaseModel):
    name: str
    description: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if not v or len(v) < 2:
            raise ValueError("Nome deve ter pelo menos 2 caracteres")
        return v


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Health check do ALB."""
    checks = {}
    try:
        await db_pool.fetchval("SELECT 1")
        checks["db"] = "ok"
    except Exception as e:
        checks["db"] = f"error: {str(e)}"

    try:
        await redis_client.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {str(e)}"

    all_ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={"status": "healthy" if all_ok else "degraded", "checks": checks}
    )


@app.get("/metrics")
async def metrics():
    """Endpoint Prometheus."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ════════════════════ PRODUTOS ════════════════════════════════════════════════════

@app.get("/catalog/products", response_model=List[ProductResponse])
async def list_products(
    category_id: Optional[str] = Query(None),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """Lista produtos com filtros opcionais."""
    timer = Timer()
    
    # Construir query dinamicamente
    where_clauses = ["p.active = true"]
    params = []
    param_count = 1

    if category_id:
        where_clauses.append(f"p.category_id = ${param_count}")
        params.append(category_id)
        param_count += 1

    if min_price is not None:
        where_clauses.append(f"p.price >= ${param_count}")
        params.append(min_price)
        param_count += 1

    if max_price is not None:
        where_clauses.append(f"p.price <= ${param_count}")
        params.append(max_price)
        param_count += 1

    where_sql = " AND ".join(where_clauses)
    offset_param = param_count
    limit_param = param_count + 1

    query = f"""
        SELECT p.id, p.sku, p.name, p.description, p.price, p.category_id, 
               c.name as category_name, p.active, p.created_at, p.updated_at
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE {where_sql}
        ORDER BY p.created_at DESC
        OFFSET ${offset_param} LIMIT ${limit_param}
    """
    
    params.extend([skip, limit])

    rows = await db_pool.fetch(query, *params)
    
    logger.info(
        "catalog.products_listed",
        extra={
            "count": len(rows),
            "filters": {
                "category_id": category_id,
                "min_price": min_price,
                "max_price": max_price,
            },
            "execution_ms": timer.elapsed_ms,
        }
    )

    return [
        ProductResponse(
            id=str(row["id"]),
            sku=row["sku"],
            name=row["name"],
            description=row["description"],
            price=float(row["price"]),
            category_id=str(row["category_id"]) if row["category_id"] else None,
            category_name=row["category_name"],
            active=row["active"],
            created_at=row["created_at"].isoformat(),
            updated_at=row["updated_at"].isoformat(),
        )
        for row in rows
    ]


@app.get("/catalog/products/{product_id}", response_model=ProductResponse)
async def get_product(product_id: str):
    """Obtém um produto por ID com cache."""
    timer = Timer()
    
    # Tentar cache
    cache_key = f"product:{product_id}"
    cached = await redis_client.get(cache_key)
    if cached:
        CACHE_HITS.labels(resource_type="product").inc()
        logger.info(
            "catalog.product_cache_hit",
            extra={"product_id": product_id}
        )
        return json.loads(cached)

    CACHE_MISSES.labels(resource_type="product").inc()

    # Buscar do banco
    row = await db_pool.fetchrow(
        """
        SELECT p.id, p.sku, p.name, p.description, p.price, p.category_id,
               c.name as category_name, p.active, p.created_at, p.updated_at
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.id = $1 AND p.active = true
        """,
        product_id,
    )

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Produto {product_id} não encontrado"
        )

    product = ProductResponse(
        id=str(row["id"]),
        sku=row["sku"],
        name=row["name"],
        description=row["description"],
        price=float(row["price"]),
        category_id=str(row["category_id"]) if row["category_id"] else None,
        category_name=row["category_name"],
        active=row["active"],
        created_at=row["created_at"].isoformat(),
        updated_at=row["updated_at"].isoformat(),
    )

    # Cachear
    await redis_client.setex(cache_key, CACHE_TTL, product.model_dump_json())

    logger.info(
        "catalog.product_fetched",
        extra={
            "product_id": product_id,
            "sku": row["sku"],
            "execution_ms": timer.elapsed_ms,
        }
    )

    return product


@app.post("/catalog/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(payload: CreateProductRequest):
    """Cria um novo produto (admin only)."""
    timer = Timer()
    product_id = str(uuid.uuid4())

    # Validar unicidade de SKU
    existing = await db_pool.fetchval(
        "SELECT id FROM products WHERE sku = $1",
        payload.sku,
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"SKU {payload.sku} já existe"
        )

    now = datetime.now(timezone.utc)

    await db_pool.execute(
        """
        INSERT INTO products (id, sku, name, description, price, category_id, active, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, $6, true, $7, $8)
        """,
        product_id,
        payload.sku,
        payload.name,
        payload.description,
        payload.price,
        payload.category_id,
        now,
        now,
    )

    # Invalidar cache de lista
    await redis_client.delete("products:list:*")

    PRODUCTS_CREATED.inc()
    PRODUCTS_TOTAL.inc()

    logger.info(
        "catalog.product_created",
        extra={
            "product_id": product_id,
            "sku": payload.sku,
            "name": payload.name,
            "price": payload.price,
            "execution_ms": timer.elapsed_ms,
        }
    )

    return ProductResponse(
        id=product_id,
        sku=payload.sku,
        name=payload.name,
        description=payload.description,
        price=payload.price,
        category_id=payload.category_id,
        category_name=None,
        active=True,
        created_at=now.isoformat(),
        updated_at=now.isoformat(),
    )


@app.patch("/catalog/products/{product_id}", response_model=ProductResponse)
async def update_product(product_id: str, payload: UpdateProductRequest):
    """Atualiza um produto existente."""
    timer = Timer()

    # Buscar produto atual
    row = await db_pool.fetchrow(
        "SELECT * FROM products WHERE id = $1",
        product_id,
    )

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Produto {product_id} não encontrado"
        )

    # Preparar UPDATE dinamicamente
    updates = []
    params = []
    param_count = 1

    if payload.name is not None:
        updates.append(f"name = ${param_count}")
        params.append(payload.name)
        param_count += 1

    if payload.description is not None:
        updates.append(f"description = ${param_count}")
        params.append(payload.description)
        param_count += 1

    if payload.price is not None:
        updates.append(f"price = ${param_count}")
        params.append(payload.price)
        param_count += 1

    if payload.category_id is not None:
        updates.append(f"category_id = ${param_count}")
        params.append(payload.category_id)
        param_count += 1

    if payload.active is not None:
        updates.append(f"active = ${param_count}")
        params.append(payload.active)
        param_count += 1

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nenhum campo para atualizar"
        )

    now = datetime.now(timezone.utc)
    updates.append(f"updated_at = ${param_count}")
    params.append(now)
    param_count += 1

    params.append(product_id)

    update_sql = ", ".join(updates)
    await db_pool.execute(
        f"UPDATE products SET {update_sql} WHERE id = ${param_count}",
        *params,
    )

    # Invalidar caches
    await redis_client.delete(f"product:{product_id}")
    await redis_client.delete("products:list:*")

    PRODUCTS_UPDATED.inc()

    # Buscar produto atualizado
    updated_row = await db_pool.fetchrow(
        """
        SELECT p.id, p.sku, p.name, p.description, p.price, p.category_id,
               c.name as category_name, p.active, p.created_at, p.updated_at
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.id = $1
        """,
        product_id,
    )

    logger.info(
        "catalog.product_updated",
        extra={
            "product_id": product_id,
            "changes": payload.model_dump(exclude_none=True),
            "execution_ms": timer.elapsed_ms,
        }
    )

    return ProductResponse(
        id=str(updated_row["id"]),
        sku=updated_row["sku"],
        name=updated_row["name"],
        description=updated_row["description"],
        price=float(updated_row["price"]),
        category_id=str(updated_row["category_id"]) if updated_row["category_id"] else None,
        category_name=updated_row["category_name"],
        active=updated_row["active"],
        created_at=updated_row["created_at"].isoformat(),
        updated_at=updated_row["updated_at"].isoformat(),
    )


@app.delete("/catalog/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(product_id: str):
    """Deleta um produto (soft delete)."""
    timer = Timer()

    row = await db_pool.fetchrow(
        "SELECT id FROM products WHERE id = $1",
        product_id,
    )

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Produto {product_id} não encontrado"
        )

    await db_pool.execute(
        "UPDATE products SET active = false, updated_at = NOW() WHERE id = $1",
        product_id,
    )

    # Invalidar caches
    await redis_client.delete(f"product:{product_id}")
    await redis_client.delete("products:list:*")

    PRODUCTS_DELETED.inc()
    PRODUCTS_TOTAL.dec()

    logger.info(
        "catalog.product_deleted",
        extra={
            "product_id": product_id,
            "execution_ms": timer.elapsed_ms,
        }
    )


# ════════════════════ CATEGORIAS ═══════════════════════════════════════════════

@app.get("/catalog/categories", response_model=List[CategoryResponse])
async def list_categories():
    """Lista todas as categorias com cache."""
    timer = Timer()
    
    # Tentar cache
    cache_key = "categories:list"
    cached = await redis_client.get(cache_key)
    if cached:
        CACHE_HITS.labels(resource_type="categories").inc()
        return json.loads(cached)

    CACHE_MISSES.labels(resource_type="categories").inc()

    rows = await db_pool.fetch(
        "SELECT id, name, description, created_at FROM categories ORDER BY name"
    )

    categories = [
        CategoryResponse(
            id=str(row["id"]),
            name=row["name"],
            description=row["description"],
            created_at=row["created_at"].isoformat(),
        )
        for row in rows
    ]

    # Cachear
    await redis_client.setex(
        cache_key,
        CACHE_TTL,
        json.dumps([c.model_dump() for c in categories], default=str),
    )

    logger.info(
        "catalog.categories_listed",
        extra={
            "count": len(categories),
            "execution_ms": timer.elapsed_ms,
        }
    )

    return categories


@app.post("/catalog/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(payload: CreateCategoryRequest):
    """Cria uma nova categoria."""
    timer = Timer()
    category_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    await db_pool.execute(
        """
        INSERT INTO categories (id, name, description, created_at)
        VALUES ($1, $2, $3, $4)
        """,
        category_id,
        payload.name,
        payload.description,
        now,
    )

    # Invalidar cache
    await redis_client.delete("categories:list")

    logger.info(
        "catalog.category_created",
        extra={
            "category_id": category_id,
            "name": payload.name,
            "execution_ms": timer.elapsed_ms,
        }
    )

    return CategoryResponse(
        id=category_id,
        name=payload.name,
        description=payload.description,
        created_at=now.isoformat(),
    )


@app.get("/catalog/search", response_model=List[ProductResponse])
async def search_products(q: str = Query(..., min_length=2)):
    """Busca produtos por nome ou SKU."""
    timer = Timer()
    search_term = f"%{q}%"

    rows = await db_pool.fetch(
        """
        SELECT p.id, p.sku, p.name, p.description, p.price, p.category_id,
               c.name as category_name, p.active, p.created_at, p.updated_at
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.active = true AND (
            LOWER(p.name) LIKE LOWER($1) OR 
            LOWER(p.sku) LIKE LOWER($1) OR
            LOWER(p.description) LIKE LOWER($1)
        )
        ORDER BY p.name
        LIMIT 50
        """,
        search_term,
    )

    logger.info(
        "catalog.search_performed",
        extra={
            "query": q,
            "results": len(rows),
            "execution_ms": timer.elapsed_ms,
        }
    )

    return [
        ProductResponse(
            id=str(row["id"]),
            sku=row["sku"],
            name=row["name"],
            description=row["description"],
            price=float(row["price"]),
            category_id=str(row["category_id"]) if row["category_id"] else None,
            category_name=row["category_name"],
            active=row["active"],
            created_at=row["created_at"].isoformat(),
            updated_at=row["updated_at"].isoformat(),
        )
        for row in rows
    ]


# ── Funções Internas ───────────────────────────────────────────────────────────

def _route_template(request: Request) -> str:
    """Template da rota para métricas."""
    route = request.scope.get("route")
    if route and getattr(route, "path", None):
        return route.path
    return request.url.path
