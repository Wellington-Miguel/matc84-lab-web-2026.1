output "user_pool_id" {
  description = "ID do Cognito User Pool"
  value       = aws_cognito_user_pool.main.id
}

output "user_pool_arn" {
  description = "ARN do Cognito User Pool"
  value       = aws_cognito_user_pool.main.arn
}

output "client_id" {
  description = "Client ID do Cognito App Client (usado no frontend para auth)"
  value       = aws_cognito_user_pool_client.api.id
}

output "issuer_url" {
  description = "Issuer JWT para validação de tokens"
  value       = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.main.id}"
}
