# =============================================================================
# Ambiente DEV — instancia o módulo canônico (modules/stack).
# Toda a definição da infraestrutura vive no módulo; aqui só entram
# os parâmetros específicos deste ambiente.
# =============================================================================
module "stack" {
  source = "../../modules/stack"

  aws_region   = var.aws_region
  project_name = var.project_name
  environment  = "dev"

  lambda_memory_mb         = var.lambda_memory_mb
  opensearch_instance_type = var.opensearch_instance_type
  log_retention_days       = var.log_retention_days
}
