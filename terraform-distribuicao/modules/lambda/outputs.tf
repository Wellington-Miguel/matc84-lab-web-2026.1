output "function_name" {
  description = "Nome da função Lambda"
  value       = aws_lambda_function.this.function_name
}

output "function_arn" {
  description = "ARN da função Lambda"
  value       = aws_lambda_function.this.arn
}

output "alias_name" {
  description = "Nome do alias live"
  value       = aws_lambda_alias.live.name
}

output "alias_arn" {
  description = "ARN do alias live (SnapStart ativo)"
  value       = aws_lambda_alias.live.arn
}

output "alias_invoke_arn" {
  description = "Invoke ARN do alias live — usado pelo API Gateway"
  value       = aws_lambda_alias.live.invoke_arn
}

output "role_arn" {
  description = "ARN da execution role"
  value       = aws_iam_role.this.arn
}

output "role_name" {
  description = "Nome da execution role"
  value       = aws_iam_role.this.name
}

output "log_group_name" {
  description = "Nome do log group CloudWatch da função"
  value       = aws_cloudwatch_log_group.this.name
}
