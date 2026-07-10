"""Pytest configuration and fixtures for integration testing"""

import os

# Must be set before any `app.*` module is imported: app.core.database builds
# its engine from settings.DATABASE_URL at import time. Without this, the
# FastAPI lifespan (triggered by TestClient as a context manager) would try
# to reach the real Postgres from docker-compose instead of a test database.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import Base, get_db
from app.models import Produto, Pedido, ItemPedido
import app.core.chaos as chaos

# Disable chaos injection during tests so results are deterministic. The chaos
# middleware randomly injects 500s and latency, which is intended for manual
# resilience experiments, not the automated test suite.
chaos.CHAOS_ENABLED = False


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
    """Create a fresh database session for each test.

    Application code (e.g. criar_pedido, store_idempotency_result) calls
    session.commit()/rollback() internally. Joining the session to the outer
    transaction via a SAVEPOINT (and restarting it after each inner
    commit/rollback) lets those internal calls behave like real checkpoints
    within the test, while the outer transaction still discards everything
    at teardown. Without this, an inner rollback (e.g. a duplicate
    idempotency key) would also wipe out earlier, already-"committed" data
    from the same test.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(autocommit=False, autoflush=False, bind=connection)()

    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess, trans):
        nonlocal nested
        if not nested.is_active:
            nested = connection.begin_nested()

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
