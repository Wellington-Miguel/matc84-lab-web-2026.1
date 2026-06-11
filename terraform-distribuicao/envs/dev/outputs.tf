output "api_endpoint" {
  description = "URL base da API"
  value       = module.stack.api_endpoint
}

output "cognito_user_pool_id" {
  description = "ID do Cognito User Pool"
  value       = module.stack.cognito_user_pool_id
}

output "cognito_client_id" {
  description = "Client ID do Cognito App Client"
  value       = module.stack.cognito_client_id
}

output "cognito_issuer_url" {
  description = "Issuer JWT para validação de tokens"
  value       = module.stack.cognito_issuer_url
}

output "opensearch_endpoint" {
  description = "Endpoint do domínio OpenSearch (acesso apenas dentro da VPC)"
  value       = module.stack.opensearch_endpoint
}

output "dynamodb_pedidos_table" {
  description = "Nome da tabela DynamoDB de pedidos"
  value       = module.stack.dynamodb_pedidos_table
}

output "dynamodb_produtos_table" {
  description = "Nome da tabela DynamoDB de produtos"
  value       = module.stack.dynamodb_produtos_table
}

output "sqs_pedidos_url" {
  description = "URL da fila SQS de pedidos"
  value       = module.stack.sqs_pedidos_url
}

output "sqs_pedidos_dlq_url" {
  description = "URL da Dead-Letter Queue"
  value       = module.stack.sqs_pedidos_dlq_url
}

output "cloudwatch_alarms_topic_arn" {
  description = "ARN do tópico SNS global de alarmes"
  value       = module.stack.cloudwatch_alarms_topic_arn
}

output "cloudwatch_dashboard_name" {
  description = "Nome do dashboard CloudWatch do projeto"
  value       = module.stack.cloudwatch_dashboard_name
}

output "vpc_id" {
  description = "ID da VPC"
  value       = module.stack.vpc_id
}

output "lambda_arns" {
  description = "ARNs dos aliases live das Lambdas"
  value = {
    auth       = module.stack.lambda_auth_arn
    pedidos    = module.stack.lambda_pedidos_arn
    produtos   = module.stack.lambda_produtos_arn
    pagamentos = module.stack.lambda_pagamentos_arn
  }
}
