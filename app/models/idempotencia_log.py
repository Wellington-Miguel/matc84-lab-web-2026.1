from datetime import datetime
import json

from sqlalchemy import Column, Integer, String, DateTime, Text, Index, LargeBinary

from app.core.database import Base


class IdempotenciaLog(Base):
    """
    Idempotency key tracking model.

    Stores processed idempotency keys to ensure idempotent operations.
    If the same key is used again, the cached response is returned.
    """
    __tablename__ = "idempotencia_log"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Idempotency tracking
    idempotencia_key = Column(String(255), nullable=False, unique=True, index=True)
    resultado = Column(Text, nullable=False)  # JSON serialized response

    # Timestamps
    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Indexes for performance
    __table_args__ = (
        Index("idx_idempotencia_key", "idempotencia_key"),
        Index("idx_idempotencia_criado_em", "criado_em"),
    )

    def __repr__(self) -> str:
        return f"<IdempotenciaLog(id={self.id}, idempotencia_key={self.idempotencia_key})>"
