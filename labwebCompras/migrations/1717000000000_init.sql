-- Up Migration

CREATE TABLE compras (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  produto      TEXT          NOT NULL,
  quantidade   INT           NOT NULL CHECK (quantidade > 0),
  valor_total  NUMERIC(12,2) NOT NULL,
  criado_em    TIMESTAMPTZ   NOT NULL DEFAULT now()
);

-- Store de idempotência: mesma chave => mesma resposta, sem duplicar compra.
CREATE TABLE idempotency_keys (
  key             UUID        PRIMARY KEY,
  request_hash    TEXT        NOT NULL,
  response_status INT,
  response_body   JSONB,
  criado_em       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Down Migration

DROP TABLE idempotency_keys;
DROP TABLE compras;
