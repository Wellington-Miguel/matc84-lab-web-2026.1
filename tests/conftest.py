"""Pytest configuration and fixtures for integration testing"""

import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import Base, get_db
from app.models import Produto, Pedido, ItemPedido


# Test database URL - use SQLite for simplicity in testing
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="session")
def engine():
    """Create test database engine"""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(engine):
    """Create a fresh database session for each test"""
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(autocommit=False, autoflush=False, bind=connection)()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(db_session: Session):
    """Create test client with overridden database dependency"""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def sample_produto(db_session: Session) -> Produto:
    """Create a sample product for testing"""
    produto = Produto(
        nome="Cerveja Premium",
        descricao="Cerveja premium artesanal",
        categoria="Bebida Alcoólica",
        preco_unitario=15.99,
        estoque_disponivel=100,
    )
    db_session.add(produto)
    db_session.commit()
    return produto


@pytest.fixture(scope="function")
def sample_produtos(db_session: Session) -> list[Produto]:
    """Create multiple sample products for testing"""
    produtos = [
        Produto(
            nome="Cerveja Premium",
            descricao="Cerveja premium artesanal",
            categoria="Bebida Alcoólica",
            preco_unitario=15.99,
            estoque_disponivel=100,
        ),
        Produto(
            nome="Refrigerante Cola",
            descricao="Refrigerante de cola",
            categoria="Refrigerante",
            preco_unitario=5.99,
            estoque_disponivel=200,
        ),
        Produto(
            nome="Suco Natural",
            descricao="Suco de laranja natural",
            categoria="Sucos",
            preco_unitario=8.99,
            estoque_disponivel=150,
        ),
    ]
    db_session.add_all(produtos)
    db_session.commit()
    return produtos
