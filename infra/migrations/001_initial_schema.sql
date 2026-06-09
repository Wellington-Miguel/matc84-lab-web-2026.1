-- migrations/001_initial_schema.sql
-- Executar uma vez na criação do banco (ou via Flyway/Alembic)

-- ── Extensões ─────────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "pgcrypto";  -- gen_random_uuid()

-- ── Clientes ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS customers (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email      VARCHAR(255) UNIQUE NOT NULL,
    name       VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Produtos / Catálogo ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS products (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sku         VARCHAR(100) UNIQUE NOT NULL,
    name        VARCHAR(255) NOT NULL,
    description TEXT,
    price       NUMERIC(12, 2) NOT NULL,
    active      BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Estoque ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS inventory (
    sku_id      UUID PRIMARY KEY REFERENCES products(id),
    quantity    INT NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    version     BIGINT NOT NULL DEFAULT 0,  -- para OCC (Optimistic Concurrency Control)
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Pedidos ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS orders (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id     UUID NOT NULL REFERENCES customers(id),
    total           NUMERIC(12, 2) NOT NULL,
    status          VARCHAR(50) NOT NULL DEFAULT 'pending',
    idempotency_key VARCHAR(255) UNIQUE,  -- chave de idempotência do pedido
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_orders_status   ON orders(status);
CREATE INDEX idx_orders_created  ON orders(created_at DESC);

-- ── Itens do Pedido ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS order_items (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id    UUID NOT NULL REFERENCES orders(id),
    sku_id      UUID NOT NULL REFERENCES products(id),
    quantity    INT NOT NULL CHECK (quantity > 0),
    unit_price  NUMERIC(12, 2) NOT NULL
);

CREATE INDEX idx_order_items_order ON order_items(order_id);

-- ── Chaves de Idempotência (protocolo Check-then-Act) ─────────────────────────
-- CRÍTICO: esta tabela evita cobranças duplicadas e pedidos em duplicidade.
CREATE TABLE IF NOT EXISTS idempotency_keys (
    key        VARCHAR(255) PRIMARY KEY,
    result     JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

-- Índice para limpeza automática de chaves expiradas
CREATE INDEX idx_idempotency_expires ON idempotency_keys(expires_at);

-- ── Pagamentos ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS payments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id        UUID NOT NULL REFERENCES orders(id),
    amount          NUMERIC(12, 2) NOT NULL,
    status          VARCHAR(50) NOT NULL DEFAULT 'pending',
    provider_ref    VARCHAR(255),   -- ID externo do gateway de pagamento
    idempotency_key VARCHAR(255) UNIQUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Trigger: atualiza updated_at automaticamente ──────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER orders_updated_at
    BEFORE UPDATE ON orders
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ── Limpeza de chaves expiradas (rode via pg_cron ou Lambda agendado) ─────────
-- DELETE FROM idempotency_keys WHERE expires_at < NOW();
