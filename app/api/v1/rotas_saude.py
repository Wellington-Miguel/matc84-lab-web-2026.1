from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.database import get_db
from app.core.chaos import chaos_faults_injected_total

router = APIRouter(prefix="", tags=["health"])

# Flag to simulate data layer failure without bringing down the physical infrastructure
SIMULAR_QUEDA_BANCO = False


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
    # Chaos injection: forces an outage state in the readiness check
    if SIMULAR_QUEDA_BANCO:
        chaos_faults_injected_total.labels("db_outage").inc()
        raise HTTPException(
            status_code=503,
            detail="💥 Chaos Engineering: Conexão com o banco de dados perdida (Falha Simulada)!",
        )

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


@router.post("/chaos/toggle-db")
async def toggle_db_chaos() -> dict:
    """
    Administrative endpoint to toggle the database failure injection.
    
    Allows testing downstream circuit breakers and load balancer behavior dynamically.
    """
    global SIMULAR_QUEDA_BANCO
    SIMULAR_QUEDA_BANCO = not SIMULAR_QUEDA_BANCO
    status = "ATIVADO" if SIMULAR_QUEDA_BANCO else "DESATIVADO"
    return {"message": f"O ataque de caos ao banco de dados foi {status}!"}