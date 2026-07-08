-- infra/migrations/02_inventory_schema.sql
-- Schema de inventário com versionamento OCC

CREATE TABLE IF NOT EXISTS inventory (
    sku_id UUID PRIMARY KEY REFERENCES products(id),
    quantity INT NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    version BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Índice para consultas rápidas por SKU
CREATE INDEX IF NOT EXISTS idx_inventory_sku_id ON inventory(sku_id);

-- Tabela de auditoria (opcional, para rastreamento)
CREATE TABLE IF NOT EXISTS inventory_audit (
    id BIGSERIAL PRIMARY KEY,
    sku_id UUID NOT NULL,
    operation VARCHAR(20) NOT NULL, -- 'DEDUCT', 'REPLENISH'
    quantity_changed INT NOT NULL,
    quantity_before INT NOT NULL,
    quantity_after INT NOT NULL,
    version INT NOT NULL,
    performed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    FOREIGN KEY (sku_id) REFERENCES inventory(sku_id)
);

CREATE INDEX IF NOT EXISTS idx_inventory_audit_sku ON inventory_audit(sku_id);
CREATE INDEX IF NOT EXISTS idx_inventory_audit_time ON inventory_audit(performed_at);

-- Dados de teste
INSERT INTO inventory (sku_id, quantity, version)
SELECT p.id, 100, 0
FROM products p
WHERE p.sku = 'CERV001'
ON CONFLICT (sku_id) DO NOTHING;

INSERT INTO inventory (sku_id, quantity, version)
SELECT p.id, 50, 0
FROM products p
WHERE p.sku = 'REFRI001'
ON CONFLICT (sku_id) DO NOTHING;

INSERT INTO inventory (sku_id, quantity, version)
SELECT p.id, 200, 0
FROM products p
WHERE p.sku = 'AGUA001'
ON CONFLICT (sku_id) DO NOTHING;
