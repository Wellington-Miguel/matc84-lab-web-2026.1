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
    ENVIRONMENT    = var.environment
    PROJECT_NAME   = var.project_name
    AWS_ACCOUNT_ID = data.aws_caller_identity.current.account_id
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

# =============================================================================
# Zip placeholder usado apenas no apply inicial das Lambdas.
# O código real (JAR) é publicado pelo CI/CD via aws lambda update-function-code.
# =============================================================================
data "archive_file" "placeholder" {
  type        = "zip"
  source_dir  = "${path.module}/../../placeholder/placeholder_src"
  output_path = "${path.module}/../../placeholder/placeholder.zip"
}
