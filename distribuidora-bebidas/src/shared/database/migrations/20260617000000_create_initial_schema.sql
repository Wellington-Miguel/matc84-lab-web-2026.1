-- Migration: Create products and idempotency_outbox tables
-- Target: PostgreSQL 16

-- 1. Create custom ENUM for idempotency status
-- This ensures type safety at the database level.
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'outbox_status') THEN
        CREATE TYPE outbox_status AS ENUM ('PROCESSING', 'COMPLETED', 'FAILED');
    END IF;
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- 2. Create products table
-- id: UUID primary key, name: product name, stock: non-negative integer,
-- version: integer for optimistic locking.
CREATE TABLE IF NOT EXISTS products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    stock INT NOT NULL DEFAULT 0,
    version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- CHECK constraint to prevent negative stock
    CONSTRAINT chk_stock_non_negative CHECK (stock >= 0)
);

-- 3. Create idempotency_outbox table
-- id: UUID primary key (used as the idempotency key), status: current processing state,
-- payload: JSONB data for the operation.
CREATE TABLE IF NOT EXISTS idempotency_outbox (
    id UUID,
    status outbox_status NOT NULL DEFAULT 'PROCESSING',
    payload JSONB NOT NULL,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP WITH TIME ZONE,
    
    -- Rigid uniqueness is enforced by the PRIMARY KEY on 'id'.
    -- Any attempt to insert a duplicate 'id' (idempotency key) will fail.
    CONSTRAINT pk_idempotency_outbox_id PRIMARY KEY (id)
);

-- Indices for optimized querying
CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);
CREATE INDEX IF NOT EXISTS idx_outbox_status ON idempotency_outbox(status) WHERE status != 'COMPLETED';

-- 4. Trigger to automatically update 'updated_at' columns
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to products
DROP TRIGGER IF EXISTS trg_products_updated_at ON products;
CREATE TRIGGER trg_products_updated_at
    BEFORE UPDATE ON products
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Apply trigger to idempotency_outbox
DROP TRIGGER IF EXISTS trg_outbox_updated_at ON idempotency_outbox;
CREATE TRIGGER trg_outbox_updated_at
    BEFORE UPDATE ON idempotency_outbox
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
