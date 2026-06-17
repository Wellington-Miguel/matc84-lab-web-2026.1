from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db, close_db
from app.api.v1 import rotas_produto, rotas_saude, rotas_pedidos
from app.services.worker_outbox import criar_tarefa_worker_outbox

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application startup and shutdown events.

    Startup: Initialize database and start background tasks
    Shutdown: Close database connections and cleanup
    """
    # Startup
    await init_db()
    print("✓ Database initialized")

    # Set up outbox worker
    criar_tarefa_worker_outbox(app, intervalo=settings.OUTBOX_WORKER_INTERVAL)
    print(f"✓ Outbox worker configured (interval: {settings.OUTBOX_WORKER_INTERVAL}s)")

    print(f"✓ Application started: {settings.PROJECT_NAME}")

    yield

    # Shutdown
    await close_db()
    print("✓ Application shutdown")


# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description="High-availability beverage distributor system - MVP",
    lifespan=lifespan,
)

# Add CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, use specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(rotas_saude.router)
app.include_router(rotas_produto.router, prefix=settings.API_V1_STR)
app.include_router(rotas_pedidos.router, prefix=settings.API_V1_STR)


@app.get("/")
async def root() -> dict:
    """Root endpoint with API information"""
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.PROJECT_VERSION,
        "status": "running",
        "docs": "/docs",
        "health": "/health",
        "ready": "/ready",
    }
