# =============================================================================
# Tabela: pedidos
# PK: pedidoId (UUID), SK: clienteId — permite query por cliente
# =============================================================================
resource "aws_dynamodb_table" "pedidos" {
  name         = "${var.prefix}-pedidos"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pedidoId"
  range_key    = "clienteId"

  attribute {
    name = "pedidoId"
    type = "S"
  }
  attribute {
    name = "clienteId"
    type = "S"
  }
  attribute {
    name = "status"
    type = "S"
  }
  attribute {
    name = "criadoEm"
    type = "S"
  }

  # GSI: busca de pedidos por cliente + status
  global_secondary_index {
    name            = "ClienteStatusIndex"
    hash_key        = "clienteId"
    range_key       = "status"
    projection_type = "ALL"
  }

  # GSI: histórico cronológico por cliente
  global_secondary_index {
    name            = "ClienteCriadoEmIndex"
    hash_key        = "clienteId"
    range_key       = "criadoEm"
    projection_type = "ALL"
  }

  # TTL para limpeza automática de pedidos cancelados expirados
  ttl {
    attribute_name = "expiresAt"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = { Name = "${var.prefix}-pedidos" }
}

# =============================================================================
# Tabela: produtos
# Catálogo de produtos da distribuidora
# =============================================================================
resource "aws_dynamodb_table" "produtos" {
  name         = "${var.prefix}-produtos"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "produtoId"

  attribute {
    name = "produtoId"
    type = "S"
  }
  attribute {
    name = "categoria"
    type = "S"
  }
  attribute {
    name = "ativo"
    type = "S"
  }

  # GSI: listagem por categoria
  global_secondary_index {
    name            = "CategoriaIndex"
    hash_key        = "categoria"
    projection_type = "ALL"
  }

  # GSI: produtos ativos (sparse index — apenas itens com `ativo = "true"`)
  global_secondary_index {
    name            = "AtivoIndex"
    hash_key        = "ativo"
    projection_type = "INCLUDE"
    non_key_attributes = [
      "produtoId", "nome", "preco", "estoque", "categoria"
    ]
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = { Name = "${var.prefix}-produtos" }
}

# =============================================================================
# Tabela: tentativas de pagamento
# PK: attemptId (UUID)
# GSI TokenIndex: busca da tentativa pelo token enviado ao cliente
# GSI OrderIdIndex: busca da tentativa mais recente pelo pedido
# =============================================================================
resource "aws_dynamodb_table" "payment_attempts" {
  name         = "${var.prefix}-payment-attempts"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "attemptId"

  attribute {
    name = "attemptId"
    type = "S"
  }
  attribute {
    name = "token"
    type = "S"
  }
  attribute {
    name = "orderId"
    type = "S"
  }
  attribute {
    name = "createdAt"
    type = "S"
  }

  global_secondary_index {
    name            = "TokenIndex"
    hash_key        = "token"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "OrderIdIndex"
    hash_key        = "orderId"
    range_key       = "createdAt"
    projection_type = "ALL"
  }

  ttl {
    attribute_name = "expiresAt"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = { Name = "${var.prefix}-payment-attempts" }
}
