# =============================================================================
# Tabela: pedidos
# PK: pedidoId (UUID), SK: clienteId — permite query por cliente
# DynamoDB Streams habilitado para eventual sincronização com Aurora
# =============================================================================
resource "aws_dynamodb_table" "pedidos" {
  name         = "${local.prefix}-pedidos"
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

  # Stream para Lambda de sincronização com Aurora
  stream_enabled   = true
  stream_view_type = "NEW_AND_OLD_IMAGES"

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

  tags = { Name = "${local.prefix}-pedidos" }
}

# =============================================================================
# Tabela: produtos
# Catálogo de produtos da distribuidora
# =============================================================================
resource "aws_dynamodb_table" "produtos" {
  name         = "${local.prefix}-produtos"
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

  tags = { Name = "${local.prefix}-produtos" }
}
