# =============================================================================
# Senha Aurora gerada pelo Terraform (nunca exposta em state legível)
# =============================================================================
resource "random_password" "aurora" {
  length           = 32
  special          = true
  override_special = "!#$%&*-_=+<>?"
}

# =============================================================================
# Secret: credenciais de acesso ao Aurora
# =============================================================================
resource "aws_secretsmanager_secret" "aurora" {
  name                    = "${local.prefix}/aurora/credentials"
  description             = "Credenciais do cluster Aurora para as Lambdas"
  recovery_window_in_days = 7
  tags                    = { Name = "${local.prefix}-aurora-secret" }
}

resource "aws_secretsmanager_secret_version" "aurora" {
  secret_id = aws_secretsmanager_secret.aurora.id

  # Formato compatível com o driver JDBC via AWS Secrets Manager rotation
  secret_string = jsonencode({
    engine   = "postgres"
    host     = aws_rds_cluster.main.endpoint
    port     = 5432
    dbname   = var.aurora_database_name
    username = "distribuicao_admin"
    password = random_password.aurora.result
  })

  # Atualiza automaticamente quando o cluster for recriado
  depends_on = [aws_rds_cluster.main]
}
