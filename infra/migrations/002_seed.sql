-- 002_seed.sql
-- Dados iniciais para desenvolvimento

-- =====================================================
-- CLIENTES
-- =====================================================

INSERT INTO customers (id, email, name)
VALUES
(
    '11111111-1111-1111-1111-111111111111',
    'joao@email.com',
    'João Silva'
),
(
    '22222222-2222-2222-2222-222222222222',
    'maria@email.com',
    'Maria Souza'
)
ON CONFLICT (id) DO NOTHING;

-- =====================================================
-- PRODUTOS
-- =====================================================

INSERT INTO products (
    id,
    sku,
    name,
    description,
    price,
    active
)
VALUES

(
    'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
    'CERV001',
    'Cerveja Pilsen 350ml',
    'Lata 350ml',
    8.50,
    TRUE
),

(
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
    'REFRI001',
    'Refrigerante Cola 2L',
    'Garrafa PET',
    12.90,
    TRUE
),

(
    'cccccccc-cccc-cccc-cccc-cccccccccccc',
    'AGUA001',
    'Água Mineral 500ml',
    'Sem gás',
    3.50,
    TRUE
)

ON CONFLICT (id) DO NOTHING;

-- =====================================================
-- ESTOQUE
-- =====================================================

INSERT INTO inventory (
    sku_id,
    quantity,
    version
)
VALUES

(
    'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
    500,
    0
),

(
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
    300,
    0
),

(
    'cccccccc-cccc-cccc-cccc-cccccccccccc',
    1000,
    0
)

ON CONFLICT (sku_id)
DO NOTHING;