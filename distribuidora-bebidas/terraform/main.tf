provider "aws" {
  region = "sa-east-1"
}

# --- Módulos Canônicos (Infra Global/Base) ---

module "canonical_network" {
  source = "./modules/canonical"
}

# --- Workloads (Específicos por Projeto/Ambiente) ---

module "sales_dev" {
  source             = "./workloads/sales/dev"
  vpc_id             = module.canonical_network.vpc_id
  public_subnet_id   = module.canonical_network.public_subnet_id
  private_subnet_ids = module.canonical_network.private_subnet_ids
}

# module "orders_dev" {
#   source = "./workloads/orders/dev"
#   ...
# }
