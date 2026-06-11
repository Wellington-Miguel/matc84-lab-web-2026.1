variable "prefix" {
  description = "Prefixo de nomes dos recursos (projeto-ambiente)"
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block da VPC"
  type        = string
}

variable "private_subnet_cidrs" {
  description = "CIDRs das subnets privadas (mínimo 2 AZs)"
  type        = list(string)
}

variable "public_subnet_cidrs" {
  description = "CIDRs das subnets públicas"
  type        = list(string)
}

variable "azs" {
  description = "Availability zones das subnets, na mesma ordem dos CIDRs"
  type        = list(string)
}
