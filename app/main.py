import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db, close_db
from app.api.v1 import rotas_produto, rotas_saude, rotas_pedidos
from app.services.worker_outbox import iniciar_worker_outbox, parar_worker_outbox
from app.core.chaos import ChaosMiddleware

logging.basicConfig(level=settings.LOG_LEVEL.upper())
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("Database initialized")

    worker_task = iniciar_worker_outbox(settings.OUTBOX_WORKER_INTERVAL)
    logger.info("Outbox worker started (interval: %ss)", settings.OUTBOX_WORKER_INTERVAL)
    logger.info("Application started: %s", settings.PROJECT_NAME)

    try:
        yield
    finally:
        await parar_worker_outbox(worker_task)
        await close_db()
        logger.info("Application shutdown")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description="High-availability beverage distributor system - MVP",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(ChaosMiddleware)
app.include_router(rotas_saude.router)
app.include_router(rotas_produto.router, prefix=settings.API_V1_STR)
app.include_router(rotas_pedidos.router, prefix=settings.API_V1_STR)


@app.get("/")
async def root() -> dict:
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.PROJECT_VERSION,
        "status": "running",
        "docs": "/docs",
        "health": "/health",
        "ready": "/ready",
    }
