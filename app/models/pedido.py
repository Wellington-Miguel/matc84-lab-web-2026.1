from datetime import datetime
from enum import Enum

from sqlalchemy import Column, Integer, String, Float, DateTime, Index, Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.core.database import Base


class StatusPedido(str, Enum):
    """Order status enumeration"""
    PENDENTE = "PENDENTE"
    CONFIRMADO = "CONFIRMADO"
    ENTREGUE = "ENTREGUE"
    CANCELADO = "CANCELADO"


class Pedido(Base):
    """
    Customer order model.

    Represents a sales order with multiple items and status tracking.
    """
    __tablename__ = "pedidos"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Order information
    cliente_id = Column(Integer, nullable=False, index=True)
    status = Column(SQLEnum(StatusPedido), default=StatusPedido.PENDENTE, nullable=False, index=True)
    total = Column(Float, nullable=False, default=0.0)

    # Timestamps
    data_pedido = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    itens = relationship("ItemPedido", back_populates="pedido", cascade="all, delete-orphan")

    # Indexes for performance
    __table_args__ = (
        Index("idx_pedido_cliente_id", "cliente_id"),
        Index("idx_pedido_status", "status"),
        Index("idx_pedido_data_pedido", "data_pedido"),
        Index("idx_pedido_criado_em", "criado_em"),
    )

    @property
    def total_itens(self) -> int:
        """Get total number of items in order"""
        return sum(item.quantidade for item in self.itens)

    def calcular_total(self) -> float:
        """Calculate total value of the order"""
        total = sum(item.subtotal for item in self.itens)
        self.total = total
        return total

    def __repr__(self) -> str:
        return f"<Pedido(id={self.id}, cliente_id={self.cliente_id}, status={self.status}, total={self.total})>"
