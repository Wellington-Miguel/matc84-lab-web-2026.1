terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  # Depois que criar o S3 bucket, descomente para salvar estado remoto:
  # backend "s3" {
  #   bucket = "bebidas-terraform-state"
  #   key    = "dev/terraform.tfstate"
  #   region = "us-east-1"
  # }
}

provider "aws" {
  region = var.aws_region
}

# ── Módulos ──────────────────────────────────────────────────────────────────

module "vpc" {
  source = "../../modules/vpc"

  project_name = var.project_name
  environment  = var.environment
  vpc_cidr     = "10.0.0.0/16"
}

module "alb" {
  source = "../../modules/alb"

  project_name   = var.project_name
  environment    = var.environment
  vpc_id         = module.vpc.vpc_id
  public_subnets = module.vpc.public_subnet_ids
}

# ── Comentado para evitar custos (ElastiCache Free Tier dura apenas 12 meses)
# module "elasticache" {
#   source = "../../modules/elasticache"
#
#   project_name    = var.project_name
#   environment     = var.environment
#   vpc_id          = module.vpc.vpc_id
#   private_subnets = module.vpc.private_subnet_ids
#   allowed_sg_id   = module.alb.alb_sg_id
# }

module "rds" {
  source = "../../modules/rds"

  project_name    = var.project_name
  environment     = var.environment
  vpc_id          = module.vpc.vpc_id
  private_subnets = module.vpc.private_subnet_ids
  allowed_sg_id   = module.alb.alb_sg_id
}

module "sqs" {
  source = "../../modules/sqs"

  project_name = var.project_name
  environment  = var.environment
}

module "asg" {
  source = "../../modules/asg"

  project_name     = var.project_name
  environment      = var.environment
  vpc_id           = module.vpc.vpc_id
  private_subnets  = module.vpc.private_subnet_ids
  alb_target_group_arn = module.alb.target_group_arn
  alb_sg_id        = module.alb.alb_sg_id
  redis_endpoint   = "" # Redis desativado para economizar custos
  db_secret_arn    = module.rds.secret_arn
}

# ── Glue Logic: Cria um novo Secret com a URL de conexão completa para o ECS ──

data "aws_secretsmanager_secret_version" "db_creds" {
  secret_id = module.rds.secret_arn
}

locals {
  db_creds_json = jsondecode(data.aws_secretsmanager_secret_version.db_creds.secret_string)
  db_url        = "postgresql://${local.db_creds_json.username}:${local.db_creds_json.password}@${module.rds.cluster_endpoint}/bebidas"
}

resource "aws_secretsmanager_secret" "db_connection_string" {
  name = "${var.project_name}-db-connection-string-${var.environment}"
}

resource "aws_secretsmanager_secret_version" "db_connection_string_version" {
  secret_id     = aws_secretsmanager_secret.db_connection_string.id
  secret_string = local.db_url
}

module "ecs" {
  source               = "../../modules/ecs"
  project_name         = var.project_name
  alb_target_group_arn = module.alb.target_group_arn
  db_connection_string_secret_arn = aws_secretsmanager_secret.db_connection_string.arn
  sqs_order_queue_url  = module.sqs.order_queue_url
}
