variable "project_name" {
  description = "Nome do projeto"
  type        = string
}

variable "environment" {
  description = "Ambiente (dev, prod)"
  type        = string
}

variable "vpc_id" {}

variable "private_subnets" {
  description = "Subnets privadas onde os servidores vão rodar"
  type        = list(string)
}

variable "alb_target_group_arn" {}

variable "alb_sg_id" {}

variable "redis_endpoint" {}

variable "db_secret_arn" {}