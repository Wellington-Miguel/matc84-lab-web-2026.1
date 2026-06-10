locals {
  # AZs derivadas da região, indexadas pelas subnets fornecidas
  azs = [
    "${var.aws_region}a",
    "${var.aws_region}b",
  ]

  # Prefixo comum para nomes de recursos
  prefix = "${var.project_name}-${var.environment}"

  # Variáveis de ambiente comuns a todas as Lambdas
  lambda_common_env = {
    ENVIRONMENT      = var.environment
    PROJECT_NAME     = var.project_name
    AWS_ACCOUNT_ID   = data.aws_caller_identity.current.account_id
    SECRET_AURORA_ARN = aws_secretsmanager_secret.aurora.arn
  }

  # Handler convention: com.<projeto>.<modulo>.Handler::handleRequest
  lambda_handlers = {
    auth       = "com.distribuicao.auth.Handler::handleRequest"
    pedidos    = "com.distribuicao.pedidos.Handler::handleRequest"
    produtos   = "com.distribuicao.produtos.Handler::handleRequest"
    pagamentos = "com.distribuicao.pagamentos.Handler::handleRequest"
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
