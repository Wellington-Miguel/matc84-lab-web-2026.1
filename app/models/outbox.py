import json
from enum import Enum

from sqlalchemy import Column, Integer, DateTime, Text, Boolean, Index, Enum as SQLEnum

from app.core.clock import utcnow
from app.core.database import Base


class TipoEvento(str, Enum):
    """Event type enumeration for outbox events"""
    PEDIDO_CRIADO = "PEDIDO_CRIADO"
    ESTOQUE_RESERVADO = "ESTOQUE_RESERVADO"
    ESTOQUE_LIBERADO = "ESTOQUE_LIBERADO"
    PEDIDO_CONFIRMADO = "PEDIDO_CONFIRMADO"
    PEDIDO_CANCELADO = "PEDIDO_CANCELADO"


class OutboxEvent(Base):
    """
    Transactional Outbox model.

    Implements the Transactional Outbox pattern for reliable event publishing.
    Events are written to the database in the same transaction as the business operation,
    then processed asynchronously by the outbox worker.

    This ensures events are never lost and operations remain idempotent.
    """
    __tablename__ = "outbox_events"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Event information
    tipo_evento = Column(SQLEnum(TipoEvento), nullable=False, index=True)
    agregado_id = Column(Integer, nullable=False, index=True)  # Related entity ID (order/product)
    dados = Column(Text, nullable=False)  # JSON serialized event data

    # Processing status
    processado = Column(Boolean, default=False, nullable=False, index=True)
    tentativas = Column(Integer, default=0, nullable=False)
    ultima_tentativa_em = Column(DateTime, nullable=True)
    erro_mensagem = Column(Text, nullable=True)

    # Timestamps
    criado_em = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)

    # Indexes for performance
    __table_args__ = (
        Index("idx_outbox_tipo_evento", "tipo_evento"),
        Index("idx_outbox_agregado_id", "agregado_id"),
        Index("idx_outbox_processado", "processado"),
        Index("idx_outbox_criado_em", "criado_em"),
        Index("idx_outbox_nao_processado", "processado", "criado_em"),  # Composite index for worker
    )

    def marcar_como_processado(self):
        """Mark this event as successfully processed"""
        self.processado = True
        self.tentativas = 0
        self.erro_mensagem = None

    def registrar_tentativa_falha(self, erro: str):
        """Register a failed processing attempt"""
        self.tentativas += 1
        self.ultima_tentativa_em = utcnow()
        self.erro_mensagem = erro

    def obter_dados(self) -> dict:
        """Parse and return the event data as dict"""
        try:
            return json.loads(self.dados)
        except json.JSONDecodeError:
            return {}

    def __repr__(self) -> str:
        return f"<OutboxEvent(id={self.id}, tipo={self.tipo_evento}, agregado_id={self.agregado_id}, processado={self.processado})>"
