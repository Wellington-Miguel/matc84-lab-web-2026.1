# =============================================================================
# Access logs do API Gateway — retenção controlada (15 dias por padrão)
# =============================================================================
resource "aws_cloudwatch_log_group" "api_gateway" {
  name              = "/aws/apigateway/${var.prefix}"
  retention_in_days = var.log_retention_days
}
