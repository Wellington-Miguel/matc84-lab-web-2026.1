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

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

from shared.logger import get_logger, LogContext, Timer

logger = get_logger("catalog-service")

# Metrics
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "path", "status"]
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds", "Request duration", ["method", "path"]
)
PRODUCTS_TOTAL = Gauge("catalog_products_total", "Active products")
CACHE_HITS = Counter("cache_hits_total", "Cache hits", ["resource_type"])
CACHE_MISSES = Counter("cache_misses_total", "Cache misses", ["resource_type"])
PRODUCTS_CREATED = Counter("products_created_total", "Products created")
PRODUCTS_UPDATED = Counter("products_updated_total", "Products updated")
PRODUCTS_DELETED = Counter("products_deleted_total", "Products deleted")

# Config
DB_URL = os.getenv("DATABASE_URL", "postgresql://bebidasadmin:[REDACTED]@localhost/bebidas")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
CACHE_TTL = 3600

# Globals
db_pool: asyncpg.Pool = None
redis_client: aioredis.Redis = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool, redis_client
    logger.info("catalog-service.starting")
    
    db_pool = await asyncpg.create_pool(DB_URL, min_size=5, max_size=20)
    redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
    
    active_products = await db_pool.fetchval("SELECT COUNT(*) FROM products WHERE active = true")
    PRODUCTS_TOTAL.set(active_products or 0)
    
    logger.info("catalog-service.ready")
    yield
    
    await db_pool.close()
    await redis_client.close()
    logger.info("catalog-service.shutdown")


app = FastAPI(title="Catalog Service", lifespan=lifespan)


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
                HTTP_REQUESTS_TOTAL.labels(method=request.method, path=path, status=str(status_code)).inc()
                HTTP_REQUEST_DURATION_SECONDS.labels(method=request.method, path=path).observe(timer.elapsed_ms / 1000)


# Models
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
            raise ValueError("SKU must be at least 3 characters")
        return v.upper()

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if not v or len(v) < 3:
            raise ValueError("Name must be at least 3 characters")
        return v

    @field_validator("price")
    @classmethod
    def validate_price(cls, v):
        if v <= 0:
            raise ValueError("Price must be positive")
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
            raise ValueError("Price must be positive")
        return round(v, 2) if v else None


class CreateCategoryRequest(BaseModel):
    name: str
    description: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if not v or len(v) < 2:
            raise ValueError("Name must be at least 2 characters")
        return v


# Endpoints
@app.get("/health")
async def health():
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
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/catalog/products", response_model=List[ProductResponse])
async def list_products(
    category_id: Optional[str] = Query(None),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    timer = Timer()
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
    query = f"""
        SELECT p.id, p.sku, p.name, p.description, p.price, p.category_id,
               c.name as category_name, p.active, p.created_at, p.updated_at
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE {where_sql}
        ORDER BY p.created_at DESC
        OFFSET ${param_count} LIMIT ${param_count + 1}
    """
    
    params.extend([skip, limit])
    rows = await db_pool.fetch(query, *params)
    
    logger.info("catalog.list_products", extra={"count": len(rows), "execution_ms": timer.elapsed_ms})
    
    return [_product_row_to_response(row) for row in rows]


@app.get("/catalog/products/{product_id}", response_model=ProductResponse)
async def get_product(product_id: str):
    timer = Timer()
    cache_key = f"product:{product_id}"
    
    cached = await redis_client.get(cache_key)
    if cached:
        CACHE_HITS.labels(resource_type="product").inc()
        return json.loads(cached)

    CACHE_MISSES.labels(resource_type="product").inc()
    
    row = await db_pool.fetchrow(
        """SELECT p.id, p.sku, p.name, p.description, p.price, p.category_id,
                  c.name as category_name, p.active, p.created_at, p.updated_at
           FROM products p
           LEFT JOIN categories c ON p.category_id = c.id
           WHERE p.id = $1 AND p.active = true""",
        product_id,
    )

    if not row:
        raise HTTPException(status_code=404, detail="Product not found")

    product = _product_row_to_response(row)
    await redis_client.setex(cache_key, CACHE_TTL, product.model_dump_json())
    
    logger.info("catalog.get_product", extra={"product_id": product_id, "execution_ms": timer.elapsed_ms})
    return product


@app.post("/catalog/products", response_model=ProductResponse, status_code=201)
async def create_product(payload: CreateProductRequest):
    timer = Timer()
    product_id = str(uuid.uuid4())

    existing = await db_pool.fetchval("SELECT id FROM products WHERE sku = $1", payload.sku)
    if existing:
        raise HTTPException(status_code=409, detail=f"SKU {payload.sku} already exists")

    now = datetime.now(timezone.utc)
    await db_pool.execute(
        """INSERT INTO products (id, sku, name, description, price, category_id, active, created_at, updated_at)
           VALUES ($1, $2, $3, $4, $5, $6, true, $7, $8)""",
        product_id, payload.sku, payload.name, payload.description, payload.price, payload.category_id, now, now,
    )

    await redis_client.delete("products:list:*")
    PRODUCTS_CREATED.inc()
    PRODUCTS_TOTAL.inc()
    
    logger.info("catalog.create_product", extra={"product_id": product_id, "sku": payload.sku, "execution_ms": timer.elapsed_ms})

    return ProductResponse(
        id=product_id, sku=payload.sku, name=payload.name, description=payload.description,
        price=payload.price, category_id=payload.category_id, category_name=None, active=True,
        created_at=now.isoformat(), updated_at=now.isoformat(),
    )


@app.patch("/catalog/products/{product_id}", response_model=ProductResponse)
async def update_product(product_id: str, payload: UpdateProductRequest):
    timer = Timer()
    row = await db_pool.fetchrow("SELECT * FROM products WHERE id = $1", product_id)
    
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")

    updates = []
    params = []
    param_count = 1

    for field, value in payload.model_dump(exclude_none=True).items():
        updates.append(f"{field} = ${param_count}")
        params.append(value)
        param_count += 1

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    now = datetime.now(timezone.utc)
    updates.append(f"updated_at = ${param_count}")
    params.append(now)
    params.append(product_id)

    await db_pool.execute(f"UPDATE products SET {', '.join(updates)} WHERE id = ${param_count + 1}", *params)

    await redis_client.delete(f"product:{product_id}")
    await redis_client.delete("products:list:*")
    PRODUCTS_UPDATED.inc()

    updated_row = await db_pool.fetchrow(
        """SELECT p.id, p.sku, p.name, p.description, p.price, p.category_id,
                  c.name as category_name, p.active, p.created_at, p.updated_at
           FROM products p
           LEFT JOIN categories c ON p.category_id = c.id
           WHERE p.id = $1""",
        product_id,
    )

    logger.info("catalog.update_product", extra={"product_id": product_id, "execution_ms": timer.elapsed_ms})
    return _product_row_to_response(updated_row)


@app.delete("/catalog/products/{product_id}", status_code=204)
async def delete_product(product_id: str):
    timer = Timer()
    row = await db_pool.fetchrow("SELECT id FROM products WHERE id = $1", product_id)
    
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")

    await db_pool.execute("UPDATE products SET active = false, updated_at = NOW() WHERE id = $1", product_id)
    
    await redis_client.delete(f"product:{product_id}")
    await redis_client.delete("products:list:*")
    PRODUCTS_DELETED.inc()
    PRODUCTS_TOTAL.dec()
    
    logger.info("catalog.delete_product", extra={"product_id": product_id, "execution_ms": timer.elapsed_ms})


@app.get("/catalog/categories", response_model=List[CategoryResponse])
async def list_categories():
    timer = Timer()
    cache_key = "categories:list"
    
    cached = await redis_client.get(cache_key)
    if cached:
        CACHE_HITS.labels(resource_type="categories").inc()
        return json.loads(cached)

    CACHE_MISSES.labels(resource_type="categories").inc()
    rows = await db_pool.fetch("SELECT id, name, description, created_at FROM categories ORDER BY name")

    categories = [
        CategoryResponse(id=str(r["id"]), name=r["name"], description=r["description"], created_at=r["created_at"].isoformat())
        for r in rows
    ]

    await redis_client.setex(cache_key, CACHE_TTL, json.dumps([c.model_dump() for c in categories], default=str))
    logger.info("catalog.list_categories", extra={"count": len(categories), "execution_ms": timer.elapsed_ms})
    
    return categories


@app.post("/catalog/categories", response_model=CategoryResponse, status_code=201)
async def create_category(payload: CreateCategoryRequest):
    timer = Timer()
    category_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    await db_pool.execute(
        "INSERT INTO categories (id, name, description, created_at) VALUES ($1, $2, $3, $4)",
        category_id, payload.name, payload.description, now,
    )

    await redis_client.delete("categories:list")
    logger.info("catalog.create_category", extra={"category_id": category_id, "name": payload.name, "execution_ms": timer.elapsed_ms})

    return CategoryResponse(id=category_id, name=payload.name, description=payload.description, created_at=now.isoformat())


@app.get("/catalog/search", response_model=List[ProductResponse])
async def search_products(q: str = Query(..., min_length=2)):
    timer = Timer()
    search_term = f"%{q}%"

    rows = await db_pool.fetch(
        """SELECT p.id, p.sku, p.name, p.description, p.price, p.category_id,
                  c.name as category_name, p.active, p.created_at, p.updated_at
           FROM products p
           LEFT JOIN categories c ON p.category_id = c.id
           WHERE p.active = true AND (LOWER(p.name) LIKE LOWER($1) OR LOWER(p.sku) LIKE LOWER($1))
           LIMIT 50""",
        search_term,
    )

    logger.info("catalog.search", extra={"query": q, "results": len(rows), "execution_ms": timer.elapsed_ms})
    return [_product_row_to_response(row) for row in rows]


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    return route.path if route and getattr(route, "path", None) else request.url.path


def _product_row_to_response(row) -> ProductResponse:
    return ProductResponse(
        id=str(row["id"]), sku=row["sku"], name=row["name"], description=row["description"],
        price=float(row["price"]), category_id=str(row["category_id"]) if row["category_id"] else None,
        category_name=row["category_name"], active=row["active"],
        created_at=row["created_at"].isoformat(), updated_at=row["updated_at"].isoformat(),
    )
