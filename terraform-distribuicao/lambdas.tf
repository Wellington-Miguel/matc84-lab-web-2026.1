# =============================================================================
# NOTA: placeholder.zip é usado apenas no terraform apply inicial.
# O deploy real do JAR é feito pelo CI/CD via:
#   aws lambda update-function-code --function-name <nome> --s3-bucket ...
# Os blocos lifecycle { ignore_changes } garantem que o Terraform não
# sobrescreva o código após o primeiro apply.
# =============================================================================

# =============================================================================
# Lambda: AUTH
# Valida tokens JWT do Cognito + consulta sessões no OpenSearch
# =============================================================================
resource "aws_cloudwatch_log_group" "lambda_auth" {
  name              = "/aws/lambda/${local.prefix}-auth"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "auth" {
  function_name = "${local.prefix}-auth"
  role          = aws_iam_role.lambda_auth.arn
  handler       = local.lambda_handlers.auth
  runtime       = var.lambda_runtime
  architectures = ["x86_64"] # SnapStart requer x86_64
  memory_size   = var.lambda_memory_mb
  timeout       = var.lambda_timeout_s
  filename      = "${path.module}/placeholder.zip"
  publish       = true # obrigatório para SnapStart

  snap_start {
    apply_on = "PublishedVersions"
  }

  vpc_config {
    subnet_ids         = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.lambda.id]
  }

  environment {
    variables = merge(local.lambda_common_env, {
      OPENSEARCH_ENDPOINT = "https://${aws_opensearch_domain.main.endpoint}"
      COGNITO_POOL_ID     = aws_cognito_user_pool.main.id
      COGNITO_CLIENT_ID   = aws_cognito_user_pool_client.api.id
      COGNITO_REGION      = var.aws_region
    })
  }

  depends_on = [aws_cloudwatch_log_group.lambda_auth]

  lifecycle {
    ignore_changes = [filename, source_code_hash, last_modified]
  }

  tags = { Name = "${local.prefix}-auth" }
}

# Alias "live" aponta para a versão publicada com SnapStart
resource "aws_lambda_alias" "auth_live" {
  name             = "live"
  function_name    = aws_lambda_function.auth.function_name
  function_version = aws_lambda_function.auth.version
}

# =============================================================================
# Lambda: PEDIDOS
# CRUD de pedidos no DynamoDB + publica eventos na fila SQS
# =============================================================================
resource "aws_cloudwatch_log_group" "lambda_pedidos" {
  name              = "/aws/lambda/${local.prefix}-pedidos"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "pedidos" {
  function_name = "${local.prefix}-pedidos"
  role          = aws_iam_role.lambda_pedidos.arn
  handler       = local.lambda_handlers.pedidos
  runtime       = var.lambda_runtime
  architectures = ["x86_64"]
  memory_size   = var.lambda_memory_mb
  timeout       = var.lambda_timeout_s
  filename      = "${path.module}/placeholder.zip"
  publish       = true

  snap_start {
    apply_on = "PublishedVersions"
  }

  vpc_config {
    subnet_ids         = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.lambda.id]
  }

  environment {
    variables = merge(local.lambda_common_env, {
      DYNAMODB_TABLE_PEDIDOS = aws_dynamodb_table.pedidos.name
      SQS_QUEUE_URL          = aws_sqs_queue.pedidos.url
    })
  }

  depends_on = [aws_cloudwatch_log_group.lambda_pedidos]

  lifecycle {
    ignore_changes = [filename, source_code_hash, last_modified]
  }

  tags = { Name = "${local.prefix}-pedidos" }
}

resource "aws_lambda_alias" "pedidos_live" {
  name             = "live"
  function_name    = aws_lambda_function.pedidos.function_name
  function_version = aws_lambda_function.pedidos.version
}

# =============================================================================
# Lambda: PRODUTOS
# Gerencia catálogo de produtos no DynamoDB
# Consumidora da fila SQS (recebe eventos de pedidos para atualizar estoque)
# =============================================================================
resource "aws_cloudwatch_log_group" "lambda_produtos" {
  name              = "/aws/lambda/${local.prefix}-produtos"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "produtos" {
  function_name = "${local.prefix}-produtos"
  role          = aws_iam_role.lambda_produtos.arn
  handler       = local.lambda_handlers.produtos
  runtime       = var.lambda_runtime
  architectures = ["x86_64"]
  memory_size   = var.lambda_memory_mb
  timeout       = var.lambda_timeout_s
  filename      = "${path.module}/placeholder.zip"
  publish       = true

  snap_start {
    apply_on = "PublishedVersions"
  }

  vpc_config {
    subnet_ids         = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.lambda.id]
  }

  environment {
    variables = merge(local.lambda_common_env, {
      DYNAMODB_TABLE_PRODUTOS = aws_dynamodb_table.produtos.name
      SQS_QUEUE_URL           = aws_sqs_queue.pedidos.url
    })
  }

  depends_on = [aws_cloudwatch_log_group.lambda_produtos]

  lifecycle {
    ignore_changes = [filename, source_code_hash, last_modified]
  }

  tags = { Name = "${local.prefix}-produtos" }
}

resource "aws_lambda_alias" "produtos_live" {
  name             = "live"
  function_name    = aws_lambda_function.produtos.function_name
  function_version = aws_lambda_function.produtos.version
}

# =============================================================================
# Event Source Mapping: SQS → Lambda produtos
#
# Implementa o elo "ReceiveMessage + DeleteMessage" do plano:
#   Lambda pedidos   →  SendMessage   →  [fila SQS]
#   [fila SQS]       →  ReceiveMessage →  Lambda produtos
#   Lambda produtos  →  DeleteMessage  →  (confirmação de sucesso)
#
# ReportBatchItemFailures
# ────────────────────────
# Sem esse modo: 1 falha no batch de 10 → todos os 10 voltam para a fila.
# Com esse modo: a Lambda retorna no body quais messageIds falharam;
# apenas esses voltam para reprocessamento. Os demais são deletados normalmente.
# Requisito: a Lambda deve retornar { batchItemFailures: [...] } no response.
#
# Batching Window
# ───────────────
# maximum_batching_window_in_seconds = 5 significa que o Lambda Poller aguarda
# até 5 segundos acumulando mensagens antes de invocar a função, otimizando
# o número de invocações (custo) sem aumentar latência perceptivelmente.
# Com 180k eventos/mês isso reduz invocações em ~40–60%.
# =============================================================================
resource "aws_lambda_event_source_mapping" "sqs_to_produtos" {
  event_source_arn = aws_sqs_queue.pedidos.arn
  function_name    = aws_lambda_alias.produtos_live.arn
  enabled          = true

  # batch_size: até 10 mensagens por invocação (máximo para SQS Standard)
  batch_size                         = 10
  maximum_batching_window_in_seconds = 5

  # Partial batch failure — só reprocessa mensagens que falharam
  function_response_types = ["ReportBatchItemFailures"]

  scaling_config {
    # Limita concorrência máxima para proteger DynamoDB de burst de escrita
    # 10 execuções × 10 msgs = 100 msgs processadas simultaneamente no pico
    maximum_concurrency = 10
  }
}

# =============================================================================
# Lambda: PAGAMENTOS
# Processa transações financeiras + atualiza status do pedido + notifica via SQS
# =============================================================================
resource "aws_cloudwatch_log_group" "lambda_pagamentos" {
  name              = "/aws/lambda/${local.prefix}-pagamentos"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "pagamentos" {
  function_name = "${local.prefix}-pagamentos"
  role          = aws_iam_role.lambda_pagamentos.arn
  handler       = local.lambda_handlers.pagamentos
  runtime       = var.lambda_runtime
  architectures = ["x86_64"]
  memory_size   = var.lambda_memory_mb
  timeout       = var.lambda_timeout_s
  filename      = "${path.module}/placeholder.zip"
  publish       = true

  snap_start {
    apply_on = "PublishedVersions"
  }

  vpc_config {
    subnet_ids         = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.lambda.id]
  }

  environment {
    variables = merge(local.lambda_common_env, {
      SQS_QUEUE_URL          = aws_sqs_queue.pedidos.url
      DYNAMODB_TABLE_PEDIDOS = aws_dynamodb_table.pedidos.name
    })
  }

  depends_on = [aws_cloudwatch_log_group.lambda_pagamentos]

  lifecycle {
    ignore_changes = [filename, source_code_hash, last_modified]
  }

  tags = { Name = "${local.prefix}-pagamentos" }
}

resource "aws_lambda_alias" "pagamentos_live" {
  name             = "live"
  function_name    = aws_lambda_function.pagamentos.function_name
  function_version = aws_lambda_function.pagamentos.version
}
