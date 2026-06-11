output "api_endpoint" {
  description = "URL base da API (ex: POST <api_endpoint>/auth/login)"
  value       = module.api_gateway.api_endpoint
}

output "cognito_user_pool_id" {
  description = "ID do Cognito User Pool"
  value       = module.auth_idp.user_pool_id
}

output "cognito_client_id" {
  description = "Client ID do Cognito App Client (usado no frontend para auth)"
  value       = module.auth_idp.client_id
}

output "cognito_issuer_url" {
  description = "Issuer JWT para validação de tokens"
  value       = module.auth_idp.issuer_url
}

output "opensearch_endpoint" {
  description = "Endpoint do domínio OpenSearch (acesso apenas dentro da VPC)"
  value       = "https://${module.search.endpoint}"
}

output "dynamodb_pedidos_table" {
  description = "Nome da tabela DynamoDB de pedidos"
  value       = module.datastore.pedidos_table_name
}

output "dynamodb_produtos_table" {
  description = "Nome da tabela DynamoDB de produtos"
  value       = module.datastore.produtos_table_name
}

output "sqs_pedidos_url" {
  description = "URL da fila SQS de pedidos"
  value       = module.messaging.queue_url
}

output "sqs_pedidos_dlq_url" {
  description = "URL da Dead-Letter Queue"
  value       = module.messaging.dlq_url
}

output "vpc_id" {
  description = "ID da VPC"
  value       = module.networking.vpc_id
}

output "private_subnet_ids" {
  description = "IDs das subnets privadas"
  value       = module.networking.private_subnet_ids
}

output "lambda_auth_arn" {
  description = "ARN do alias live da Lambda auth"
  value       = module.lambda_auth.alias_arn
}

output "lambda_pedidos_arn" {
  description = "ARN do alias live da Lambda pedidos"
  value       = module.lambda_pedidos.alias_arn
}

output "lambda_produtos_arn" {
  description = "ARN do alias live da Lambda produtos"
  value       = module.lambda_produtos.alias_arn
}

output "lambda_pagamentos_arn" {
  description = "ARN do alias live da Lambda pagamentos"
  value       = module.lambda_pagamentos.alias_arn
}
