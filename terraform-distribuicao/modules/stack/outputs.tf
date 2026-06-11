output "api_endpoint" {
  description = "URL base da API (ex: POST <api_endpoint>/auth/login)"
  value       = module.api_gateway.api_endpoint
}

output "cognito_user_pool_id" {
  description = "ID do Cognito User Pool"
  value       = module.cognito.user_pool_id
}

output "cognito_client_id" {
  description = "Client ID do Cognito App Client (usado no frontend para auth)"
  value       = module.cognito.client_id
}

output "cognito_issuer_url" {
  description = "Issuer JWT para validação de tokens"
  value       = module.cognito.issuer_url
}

output "opensearch_endpoint" {
  description = "Endpoint do domínio OpenSearch (acesso apenas dentro da VPC)"
  value       = "https://${module.opensearch.endpoint}"
}

output "dynamodb_pedidos_table" {
  description = "Nome da tabela DynamoDB de pedidos"
  value       = module.dynamodb.pedidos_table_name
}

output "dynamodb_produtos_table" {
  description = "Nome da tabela DynamoDB de produtos"
  value       = module.dynamodb.produtos_table_name
}

output "sqs_pedidos_url" {
  description = "URL da fila SQS de pedidos"
  value       = module.sqs.queue_url
}

output "sqs_pedidos_dlq_url" {
  description = "URL da Dead-Letter Queue"
  value       = module.sqs.dlq_url
}

output "cloudwatch_alarms_topic_arn" {
  description = "ARN do tópico SNS global de alarmes"
  value       = module.cloudwatch.sns_topic_arn
}

output "cloudwatch_dashboard_name" {
  description = "Nome do dashboard CloudWatch do projeto"
  value       = module.cloudwatch.dashboard_name
}

output "vpc_id" {
  description = "ID da VPC"
  value       = module.vpc.vpc_id
}

output "private_subnet_ids" {
  description = "IDs das subnets privadas"
  value       = module.vpc.private_subnet_ids
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
