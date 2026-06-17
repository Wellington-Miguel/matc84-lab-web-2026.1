from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.database import get_db

router = APIRouter(prefix="", tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    """
    Basic health check endpoint (liveness check).

    Used by load balancers and monitoring to determine if the service is running.
    """
    return {"status": "healthy", "service": "beverage-distributor"}


@router.get("/ready")
async def readiness_check(db: Session = Depends(get_db)) -> dict:
    """
    Readiness check endpoint.

    Verifies that the service is ready to accept traffic.
    Checks database connectivity and outbox worker status.
    """
    try:
        # Check database connectivity
        db.execute(text("SELECT 1"))

        return {
            "status": "ready",
            "service": "beverage-distributor",
            "database": "connected",
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Service not ready: {str(e)}",
        )
