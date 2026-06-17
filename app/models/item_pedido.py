from sqlalchemy import Column, Integer, Float, ForeignKey, Index
from sqlalchemy.orm import relationship

from app.core.database import Base


class ItemPedido(Base):
    """
    Order line item model.

    Represents individual items in an order with quantity and pricing.
    """
    __tablename__ = "itens_pedido"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Foreign keys
    pedido_id = Column(Integer, ForeignKey("pedidos.id", ondelete="CASCADE"), nullable=False, index=True)
    produto_id = Column(Integer, ForeignKey("produtos.id", ondelete="RESTRICT"), nullable=False, index=True)

    # Order item details
    quantidade = Column(Integer, nullable=False)
    preco_unitario = Column(Float, nullable=False)

    # Relationships
    pedido = relationship("Pedido", back_populates="itens")
    produto = relationship("Produto", back_populates="itens_pedido")

    # Indexes for performance
    __table_args__ = (
        Index("idx_item_pedido_pedido_id", "pedido_id"),
        Index("idx_item_pedido_produto_id", "produto_id"),
    )

    @property
    def subtotal(self) -> float:
        """Calculate subtotal for this line item"""
        return self.quantidade * self.preco_unitario

    def __repr__(self) -> str:
        return f"<ItemPedido(id={self.id}, pedido_id={self.pedido_id}, produto_id={self.produto_id}, quantidade={self.quantidade})>"
