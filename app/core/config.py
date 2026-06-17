import os
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool


class Settings:
    """Application configuration from environment variables"""

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://admin:adminpassword@localhost:5432/distribuidora"
    )

    # API
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Beverage Distributor System"
    PROJECT_VERSION: str = "0.1.0"

    # Server
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Connection pooling
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "5"))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    DB_POOL_TIMEOUT: int = int(os.getenv("DB_POOL_TIMEOUT", "30"))
    DB_POOL_RECYCLE: int = int(os.getenv("DB_POOL_RECYCLE", "3600"))  # 1 hour

    # Pagination
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    # Outbox worker
    OUTBOX_WORKER_INTERVAL: int = int(os.getenv("OUTBOX_WORKER_INTERVAL", "5"))  # seconds


def get_settings() -> Settings:
    """Get application settings"""
    return Settings()


def get_database_engine():
    """Create SQLAlchemy engine with connection pooling"""
    settings = get_settings()

    engine = create_engine(
        settings.DATABASE_URL,
        poolclass=QueuePool,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT,
        pool_recycle=settings.DB_POOL_RECYCLE,
        echo=settings.DEBUG,
    )

    return engine


settings = get_settings()
