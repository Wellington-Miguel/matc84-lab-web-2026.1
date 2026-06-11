# =============================================================================
# Composição da infraestrutura — todos os componentes são módulos.
# Workloads Lambda são instâncias do módulo canônico lambda-workload.
# =============================================================================

module "networking" {
  source = "../networking"

  prefix               = local.prefix
  vpc_cidr             = var.vpc_cidr
  private_subnet_cidrs = var.private_subnet_cidrs
  public_subnet_cidrs  = var.public_subnet_cidrs
  azs                  = local.azs
}

module "auth_idp" {
  source = "../auth"

  prefix     = local.prefix
  aws_region = var.aws_region
}

module "datastore" {
  source = "../datastore"

  prefix = local.prefix
}

module "messaging" {
  source = "../messaging"

  prefix                 = local.prefix
  visibility_timeout_s   = var.sqs_visibility_timeout_s
  message_retention_days = var.sqs_message_retention_days
  max_receive_count      = var.sqs_max_receive_count
}

module "search" {
  source = "../search"

  prefix               = local.prefix
  instance_type        = var.opensearch_instance_type
  volume_gb            = var.opensearch_volume_gb
  subnet_ids           = module.networking.private_subnet_ids
  security_group_ids   = [module.networking.opensearch_security_group_id]
  master_user_role_arn = module.lambda_auth.role_arn
  log_retention_days   = var.log_retention_days
}

# =============================================================================
# Workloads Lambda (módulo canônico)
# =============================================================================

# Auth: valida tokens JWT do Cognito + consulta sessões no OpenSearch
module "lambda_auth" {
  source = "../lambda-workload"

  function_name      = "${local.prefix}-auth"
  handler            = local.lambda_handlers.auth
  runtime            = var.lambda_runtime
  memory_size        = var.lambda_memory_mb
  timeout            = var.lambda_timeout_s
  filename           = data.archive_file.placeholder.output_path
  subnet_ids         = module.networking.private_subnet_ids
  security_group_ids = [module.networking.lambda_security_group_id]
  log_retention_days = var.log_retention_days

  environment_variables = merge(local.lambda_common_env, {
    OPENSEARCH_ENDPOINT = "https://${module.search.endpoint}"
    COGNITO_POOL_ID     = module.auth_idp.user_pool_id
    COGNITO_CLIENT_ID   = module.auth_idp.client_id
    COGNITO_REGION      = var.aws_region
  })

  policy_statements = [
    {
      sid = "OpenSearch"
      actions = [
        "es:ESHttpGet",
        "es:ESHttpPost",
        "es:ESHttpPut",
        "es:ESHttpDelete",
      ]
      resources = ["${module.search.domain_arn}/*"]
    },
    {
      sid = "CognitoIDP"
      actions = [
        "cognito-idp:GetUser",
        "cognito-idp:AdminGetUser",
      ]
      resources = [module.auth_idp.user_pool_arn]
    },
  ]
}

# Pedidos: CRUD de pedidos no DynamoDB + publica eventos na fila SQS
module "lambda_pedidos" {
  source = "../lambda-workload"

  function_name      = "${local.prefix}-pedidos"
  handler            = local.lambda_handlers.pedidos
  runtime            = var.lambda_runtime
  memory_size        = var.lambda_memory_mb
  timeout            = var.lambda_timeout_s
  filename           = data.archive_file.placeholder.output_path
  subnet_ids         = module.networking.private_subnet_ids
  security_group_ids = [module.networking.lambda_security_group_id]
  log_retention_days = var.log_retention_days

  environment_variables = merge(local.lambda_common_env, {
    DYNAMODB_TABLE_PEDIDOS = module.datastore.pedidos_table_name
    SQS_QUEUE_URL          = module.messaging.queue_url
  })

  policy_statements = [
    {
      sid = "DynamoDBPedidos"
      actions = [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem",
        "dynamodb:Query",
        "dynamodb:TransactWriteItems",
      ]
      resources = [
        module.datastore.pedidos_table_arn,
        "${module.datastore.pedidos_table_arn}/index/*",
      ]
    },
    {
      sid       = "SQSSend"
      actions   = ["sqs:SendMessage", "sqs:GetQueueUrl"]
      resources = [module.messaging.queue_arn]
    },
  ]
}

# Produtos: catálogo no DynamoDB + consumidora da fila SQS (eventos de pedidos)
module "lambda_produtos" {
  source = "../lambda-workload"

  function_name      = "${local.prefix}-produtos"
  handler            = local.lambda_handlers.produtos
  runtime            = var.lambda_runtime
  memory_size        = var.lambda_memory_mb
  timeout            = var.lambda_timeout_s
  filename           = data.archive_file.placeholder.output_path
  subnet_ids         = module.networking.private_subnet_ids
  security_group_ids = [module.networking.lambda_security_group_id]
  log_retention_days = var.log_retention_days

  environment_variables = merge(local.lambda_common_env, {
    DYNAMODB_TABLE_PRODUTOS = module.datastore.produtos_table_name
    SQS_QUEUE_URL           = module.messaging.queue_url
  })

  policy_statements = [
    {
      sid = "DynamoDBProdutos"
      actions = [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:Query",
        "dynamodb:Scan",
        "dynamodb:BatchGetItem",
      ]
      resources = [
        module.datastore.produtos_table_arn,
        "${module.datastore.produtos_table_arn}/index/*",
      ]
    },
    {
      sid = "SQSConsume"
      actions = [
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:GetQueueAttributes",
        "sqs:ChangeMessageVisibility",
      ]
      resources = [module.messaging.queue_arn]
    },
  ]
}

# Pagamentos: processa transações + atualiza status do pedido + notifica via SQS
module "lambda_pagamentos" {
  source = "../lambda-workload"

  function_name      = "${local.prefix}-pagamentos"
  handler            = local.lambda_handlers.pagamentos
  runtime            = var.lambda_runtime
  memory_size        = var.lambda_memory_mb
  timeout            = var.lambda_timeout_s
  filename           = data.archive_file.placeholder.output_path
  subnet_ids         = module.networking.private_subnet_ids
  security_group_ids = [module.networking.lambda_security_group_id]
  log_retention_days = var.log_retention_days

  environment_variables = merge(local.lambda_common_env, {
    SQS_QUEUE_URL          = module.messaging.queue_url
    DYNAMODB_TABLE_PEDIDOS = module.datastore.pedidos_table_name
  })

  policy_statements = [
    {
      sid       = "SQSSend"
      actions   = ["sqs:SendMessage", "sqs:GetQueueUrl"]
      resources = [module.messaging.queue_arn]
    },
    {
      sid = "DynamoDBPedidosUpdate"
      actions = [
        "dynamodb:UpdateItem",
        "dynamodb:GetItem",
      ]
      resources = [module.datastore.pedidos_table_arn]
    },
  ]
}

# =============================================================================
# Event Source Mapping: SQS → Lambda produtos
#
# Implementa o elo "ReceiveMessage + DeleteMessage" do plano:
#   Lambda pedidos   →  SendMessage    →  [fila SQS]
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
  event_source_arn = module.messaging.queue_arn
  function_name    = module.lambda_produtos.alias_arn
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
# API Gateway — entry point HTTP integrando os 4 workloads
# =============================================================================
module "api_gateway" {
  source = "../api-gateway"

  prefix             = local.prefix
  stage_name         = var.environment
  cognito_client_id  = module.auth_idp.client_id
  cognito_issuer_url = module.auth_idp.issuer_url
  log_retention_days = var.log_retention_days

  lambda_integrations = {
    auth = {
      function_name    = module.lambda_auth.function_name
      alias_name       = module.lambda_auth.alias_name
      alias_invoke_arn = module.lambda_auth.alias_invoke_arn
    }
    pedidos = {
      function_name    = module.lambda_pedidos.function_name
      alias_name       = module.lambda_pedidos.alias_name
      alias_invoke_arn = module.lambda_pedidos.alias_invoke_arn
    }
    produtos = {
      function_name    = module.lambda_produtos.function_name
      alias_name       = module.lambda_produtos.alias_name
      alias_invoke_arn = module.lambda_produtos.alias_invoke_arn
    }
    pagamentos = {
      function_name    = module.lambda_pagamentos.function_name
      alias_name       = module.lambda_pagamentos.alias_name
      alias_invoke_arn = module.lambda_pagamentos.alias_invoke_arn
    }
  }
}
