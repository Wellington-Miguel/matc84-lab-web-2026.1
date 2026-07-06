provider "aws" {
  region = "sa-east-1"
}

variable "db_password" {
  type      = string
  sensitive = true
  description = "Password for the RDS instance"
}

variable "allowed_ssh_cidr_blocks" {
  type        = list(string)
  description = "CIDR blocks allowed to SSH into the sales EC2 instance. Restrict to trusted IP ranges."
}

# --- Módulos Canônicos (Infra Global/Base) ---

module "canonical_network" {
  source = "./modules/canonical"
}

# --- Workloads (Específicos por Projeto/Ambiente) ---

module "sales_dev" {
  source                  = "./workloads/sales/dev"
  vpc_id                  = module.canonical_network.vpc_id
  public_subnet_id        = module.canonical_network.public_subnet_id
  private_subnet_ids      = module.canonical_network.private_subnet_ids
  db_password             = var.db_password
  allowed_ssh_cidr_blocks = var.allowed_ssh_cidr_blocks
}

# module "orders_dev" {
#   source = "./workloads/orders/dev"
#   ...
# }
