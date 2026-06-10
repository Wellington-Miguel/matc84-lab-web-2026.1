output "api_endpoint" {
  description = "URL base da API (ex: POST ${api_endpoint}/auth/login)"
  value       = aws_apigatewayv2_stage.main.invoke_url
}

output "cognito_user_pool_id" {
  description = "ID do Cognito User Pool"
  value       = aws_cognito_user_pool.main.id
}

output "cognito_client_id" {
  description = "Client ID do Cognito App Client (usado no frontend para auth)"
  value       = aws_cognito_user_pool_client.api.id
}

output "cognito_issuer_url" {
  description = "Issuer JWT para validação de tokens"
  value       = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.main.id}"
}

output "opensearch_endpoint" {
  description = "Endpoint do domínio OpenSearch (acesso apenas dentro da VPC)"
  value       = "https://${aws_opensearch_domain.main.endpoint}"
}

output "aurora_endpoint" {
  description = "Endpoint de escrita do cluster Aurora"
  value       = aws_rds_cluster.main.endpoint
  sensitive   = true
}

output "aurora_reader_endpoint" {
  description = "Endpoint de leitura do cluster Aurora"
  value       = aws_rds_cluster.main.reader_endpoint
  sensitive   = true
}

output "aurora_secret_arn" {
  description = "ARN do Secret com credenciais Aurora"
  value       = aws_secretsmanager_secret.aurora.arn
}

output "dynamodb_pedidos_table" {
  description = "Nome da tabela DynamoDB de pedidos"
  value       = aws_dynamodb_table.pedidos.name
}

output "dynamodb_produtos_table" {
  description = "Nome da tabela DynamoDB de produtos"
  value       = aws_dynamodb_table.produtos.name
}

output "sqs_pedidos_url" {
  description = "URL da fila SQS de pedidos"
  value       = aws_sqs_queue.pedidos.url
}

output "sqs_pedidos_dlq_url" {
  description = "URL da Dead-Letter Queue"
  value       = aws_sqs_queue.pedidos_dlq.url
}

output "vpc_id" {
  description = "ID da VPC"
  value       = aws_vpc.main.id
}

output "private_subnet_ids" {
  description = "IDs das subnets privadas"
  value       = aws_subnet.private[*].id
}

output "lambda_auth_arn" {
  description = "ARN do alias live da Lambda auth"
  value       = aws_lambda_alias.auth_live.arn
}

output "lambda_pedidos_arn" {
  description = "ARN do alias live da Lambda pedidos"
  value       = aws_lambda_alias.pedidos_live.arn
}

output "lambda_produtos_arn" {
  description = "ARN do alias live da Lambda produtos"
  value       = aws_lambda_alias.produtos_live.arn
}

output "lambda_pagamentos_arn" {
  description = "ARN do alias live da Lambda pagamentos"
  value       = aws_lambda_alias.pagamentos_live.arn
}
