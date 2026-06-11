# =============================================================================
# Log group da função — criado explicitamente para controlar a retenção.
# Estratégia de expiração de logs aplicada via retention_in_days (15 dias).
# =============================================================================
resource "aws_cloudwatch_log_group" "this" {
  name              = "/aws/lambda/${var.function_name}"
  retention_in_days = var.log_retention_days
}
