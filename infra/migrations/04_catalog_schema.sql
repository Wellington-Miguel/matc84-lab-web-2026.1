-- infra/migrations/04_catalog_schema.sql
-- Schema de catálogo com produtos e categorias

CREATE TABLE IF NOT EXISTS categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_categories_name ON categories(LOWER(name));

-- Tabela de produtos
CREATE TABLE IF NOT EXISTS products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sku VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price NUMERIC(12, 2) NOT NULL CHECK (price > 0),
    category_id UUID REFERENCES categories(id) ON DELETE SET NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_products_sku ON products(LOWER(sku));
CREATE INDEX IF NOT EXISTS idx_products_name ON products(LOWER(name));
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_products_is_active ON products(is_active);
CREATE INDEX IF NOT EXISTS idx_products_created_at ON products(created_at DESC);

-- Dados de teste
INSERT INTO categories (id, name, description) VALUES
    (gen_random_uuid(), 'Cervejas', 'Bebidas alcoólicas tipo cerveja'),
    (gen_random_uuid(), 'Refrigerantes', 'Bebidas gaseificadas'),
    (gen_random_uuid(), 'Sucos', 'Sucos naturais e industrializados'),
    (gen_random_uuid(), 'Chás', 'Bebidas quentes e frias'),
    (gen_random_uuid(), 'Energia', 'Bebidas energéticas')
ON CONFLICT DO NOTHING;

-- Inserir produtos de exemplo
WITH categories_cte AS (
    SELECT id FROM categories WHERE name IN ('Cervejas', 'Refrigerantes', 'Energia')
)
INSERT INTO products (sku, name, description, price, category_id, is_active) 
SELECT 
    'CERV-001', 'Cerveja Pilsen 350ml', 'Cerveja clara tipo pilsen', 5.50, 
    (SELECT id FROM categories WHERE name = 'Cervejas'), true
UNION ALL SELECT
    'CERV-002', 'Cerveja IPA 500ml', 'Cerveja artesanal IPA', 12.00,
    (SELECT id FROM categories WHERE name = 'Cervejas'), true
UNION ALL SELECT
    'REFRI-001', 'Refrigerante Cola 2L', 'Refrigerante à base de cola', 8.50,
    (SELECT id FROM categories WHERE name = 'Refrigerantes'), true
UNION ALL SELECT
    'REFRI-002', 'Refrigerante Laranja 1.5L', 'Refrigerante sabor laranja', 6.50,
    (SELECT id FROM categories WHERE name = 'Refrigerantes'), true
UNION ALL SELECT
    'ENER-001', 'Bebida Energética 250ml', 'Bebida energética premium', 9.00,
    (SELECT id FROM categories WHERE name = 'Energia'), true
ON CONFLICT (sku) DO NOTHING;
