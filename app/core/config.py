import os


class Settings:
    """Application configuration from environment variables"""

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://admin:adminpassword@localhost:5432/distribuidora",
    )

    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Beverage Distributor System"
    PROJECT_VERSION: str = "0.1.0"

    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "5"))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    DB_POOL_TIMEOUT: int = int(os.getenv("DB_POOL_TIMEOUT", "30"))
    DB_POOL_RECYCLE: int = int(os.getenv("DB_POOL_RECYCLE", "3600"))

    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    OUTBOX_WORKER_INTERVAL: int = int(os.getenv("OUTBOX_WORKER_INTERVAL", "5"))

    # Chaos Engineering. Disabled by default so fault injection is never active
    # unless explicitly enabled for an experiment. Accept the common truthy
    # spellings so CHAOS_ENABLED=1/yes/on also enable it (not just "true").
    CHAOS_ENABLED: bool = os.getenv("CHAOS_ENABLED", "false").lower() in {
        "true", "1", "yes", "on",
    }
    CHAOS_ERROR_RATE: float = float(os.getenv("CHAOS_ERROR_RATE", "0.2"))
    CHAOS_LATENCY_RATE: float = float(os.getenv("CHAOS_LATENCY_RATE", "0.3"))
    CHAOS_MIN_LATENCY: float = float(os.getenv("CHAOS_MIN_LATENCY", "1.0"))
    CHAOS_MAX_LATENCY: float = float(os.getenv("CHAOS_MAX_LATENCY", "3.0"))


settings = Settings()
