from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, DateTime, Index
from sqlalchemy.orm import relationship

from app.core.database import Base


class Produto(Base):
    """
    Beverage product model.

    Stores information about available beverages in inventory.
    """
    __tablename__ = "produtos"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Basic information
    nome = Column(String(255), nullable=False, index=True)
    descricao = Column(String(1024), nullable=True)
    categoria = Column(String(100), nullable=False, index=True)

    # Pricing and inventory
    preco_unitario = Column(Float, nullable=False)
    estoque_disponivel = Column(Integer, nullable=False, default=0)

    # Timestamps
    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    itens_pedido = relationship("ItemPedido", back_populates="produto", cascade="all, delete-orphan")

    # Indexes for performance
    __table_args__ = (
        Index("idx_produto_categoria", "categoria"),
        Index("idx_produto_estoque", "estoque_disponivel"),
        Index("idx_produto_criado_em", "criado_em"),
    )

    def __repr__(self) -> str:
        return f"<Produto(id={self.id}, nome={self.nome}, estoque={self.estoque_disponivel})>"
