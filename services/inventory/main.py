import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

import asyncpg
import redis.asyncio as aioredis
from fastapi import FastAPI, Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, Gauge, generate_latest
from pydantic import BaseModel, field_validator

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

from shared.logger import get_logger, LogContext, Timer

logger = get_logger("inventory-service")

# Metrics
HTTP_REQUESTS_TOTAL = Counter("http_requests_total", "HTTP requests", ["method", "path", "status"])
HTTP_REQUEST_DURATION_SECONDS = Histogram("http_request_duration_seconds", "Request duration", ["method", "path"])
STOCK_LEVEL = Gauge("inventory_stock_level", "Stock level by product", ["sku_id"])
STOCK_DEDUCTION_TOTAL = Counter("stock_deduction_total", "Stock deductions", ["result"])
OCC_CONFLICT_TOTAL = Counter("occ_conflict_total", "OCC conflicts", ["sku_id"])

# Config
DB_URL = os.getenv("DATABASE_URL", "postgresql://bebidasadmin:[REDACTED]@localhost/bebidas")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Globals
db_pool: asyncpg.Pool = None
redis_client: aioredis.Redis = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool, redis_client
    logger.info("inventory-service.starting")
    
    db_pool = await asyncpg.create_pool(DB_URL, min_size=5, max_size=20)
    redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
    
    logger.info("inventory-service.ready")
    yield
    
    await db_pool.close()
    await redis_client.close()
    logger.info("inventory-service.shutdown")


app = FastAPI(title="Inventory Service", lifespan=lifespan)


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
class DeductStockRequest(BaseModel):
    quantity: int
    
    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, v):
        if v <= 0:
            raise ValueError("Quantity must be positive")
        return v


class ReplenishStockRequest(BaseModel):
    quantity: int
    
    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, v):
        if v <= 0:
            raise ValueError("Quantity must be positive")
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


@app.get("/inventory/{product_id}")
async def get_inventory(product_id: str):
    timer = Timer()
    row = await db_pool.fetchrow(
        "SELECT sku_id, quantity, version, updated_at FROM inventory WHERE sku_id = $1::uuid",
        product_id,
    )
    
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")

    STOCK_LEVEL.labels(sku_id=str(row["sku_id"])).set(row["quantity"])
    logger.info("inventory.get", extra={"product_id": product_id, "execution_ms": timer.elapsed_ms})
    
    return {
        "sku_id": str(row["sku_id"]),
        "quantity": row["quantity"],
        "version": row["version"],
        "updated_at": row["updated_at"].isoformat(),
    }


@app.post("/inventory/{product_id}/deduct", status_code=200)
async def deduct_stock(product_id: str, payload: DeductStockRequest):
    timer = Timer()
    max_retries = 3
    attempt = 0

    while attempt < max_retries:
        attempt += 1
        current = await _get_stock_with_version(product_id)
        
        if not current:
            STOCK_DEDUCTION_TOTAL.labels(result="not_found").inc()
            raise HTTPException(status_code=404, detail="Product not found")

        if current["quantity"] < payload.quantity:
            STOCK_DEDUCTION_TOTAL.labels(result="insufficient").inc()
            raise HTTPException(status_code=409, detail=f"Insufficient stock: {current['quantity']} available")

        new_quantity = current["quantity"] - payload.quantity
        new_version = current["version"] + 1

        rows_updated = await db_pool.execute(
            "UPDATE inventory SET quantity = $1, version = $2, updated_at = NOW() WHERE sku_id = $3::uuid AND version = $4",
            new_quantity, new_version, product_id, current["version"],
        )

        if rows_updated == "UPDATE 1":
            await redis_client.setex(f"stock:{product_id}", 60, f"{new_quantity}:{new_version}")
            STOCK_LEVEL.labels(sku_id=product_id).set(new_quantity)
            STOCK_DEDUCTION_TOTAL.labels(result="success").inc()
            
            logger.info("inventory.deduct", extra={
                "product_id": product_id, "deducted": payload.quantity,
                "remaining": new_quantity, "attempt": attempt, "execution_ms": timer.elapsed_ms
            })
            
            return {"sku_id": product_id, "deducted": payload.quantity, "remaining": new_quantity, "version": new_version}

        OCC_CONFLICT_TOTAL.labels(sku_id=product_id).inc()
        await redis_client.delete(f"stock:{product_id}")

    STOCK_DEDUCTION_TOTAL.labels(result="conflict").inc()
    raise HTTPException(status_code=409, detail=f"Failed after {max_retries} attempts")


@app.post("/inventory/{product_id}/replenish", status_code=200)
async def replenish_stock(product_id: str, payload: ReplenishStockRequest):
    timer = Timer()
    row = await db_pool.fetchrow("SELECT quantity FROM inventory WHERE sku_id = $1::uuid", product_id)
    
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")

    new_quantity = row["quantity"] + payload.quantity
    await db_pool.execute("UPDATE inventory SET quantity = $1, updated_at = NOW() WHERE sku_id = $2::uuid", new_quantity, product_id)

    await redis_client.delete(f"stock:{product_id}")
    STOCK_LEVEL.labels(sku_id=product_id).set(new_quantity)

    logger.info("inventory.replenish", extra={"product_id": product_id, "added": payload.quantity, "execution_ms": timer.elapsed_ms})

    return {"sku_id": product_id, "added": payload.quantity, "total": new_quantity}


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    return route.path if route and getattr(route, "path", None) else request.url.path


async def _get_stock_with_version(product_id: str) -> Optional[dict]:
    cached = await redis_client.get(f"stock:{product_id}")
    if cached:
        qty_str, version_str = cached.split(":")
        return {"quantity": int(qty_str), "version": int(version_str)}

    row = await db_pool.fetchrow("SELECT quantity, version FROM inventory WHERE sku_id = $1::uuid", product_id)
    if row:
        await redis_client.setex(f"stock:{product_id}", 60, f"{row['quantity']}:{row['version']}")
        return {"quantity": row["quantity"], "version": row["version"]}

    return None
