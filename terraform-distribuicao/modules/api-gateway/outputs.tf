output "api_endpoint" {
  description = "URL base da API (invoke URL do stage)"
  value       = aws_apigatewayv2_stage.main.invoke_url
}

output "api_id" {
  description = "ID do HTTP API"
  value       = aws_apigatewayv2_api.main.id
}

output "execution_arn" {
  description = "Execution ARN do HTTP API"
  value       = aws_apigatewayv2_api.main.execution_arn
}
