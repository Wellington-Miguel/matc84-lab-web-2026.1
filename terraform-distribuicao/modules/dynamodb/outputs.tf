output "pedidos_table_name" {
  description = "Nome da tabela DynamoDB de pedidos"
  value       = aws_dynamodb_table.pedidos.name
}

output "pedidos_table_arn" {
  description = "ARN da tabela DynamoDB de pedidos"
  value       = aws_dynamodb_table.pedidos.arn
}

output "produtos_table_name" {
  description = "Nome da tabela DynamoDB de produtos"
  value       = aws_dynamodb_table.produtos.name
}

output "produtos_table_arn" {
  description = "ARN da tabela DynamoDB de produtos"
  value       = aws_dynamodb_table.produtos.arn
}
