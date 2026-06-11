variable "prefix" {
  description = "Prefixo de nomes dos recursos (projeto-ambiente)"
  type        = string
}

variable "instance_type" {
  description = "Tipo de instância do OpenSearch"
  type        = string
  default     = "t3.small.search"
}

variable "volume_gb" {
  description = "Tamanho do volume EBS do OpenSearch (GB)"
  type        = number
  default     = 20
}

variable "subnet_ids" {
  description = "Subnets do domínio (single-node usa apenas a primeira)"
  type        = list(string)
}

variable "security_group_ids" {
  description = "Security groups do domínio"
  type        = list(string)
}

variable "master_user_role_arn" {
  description = "ARN da IAM role com acesso master ao domínio (Lambda auth)"
  type        = string
}

variable "log_retention_days" {
  description = "Retenção dos slow logs no CloudWatch (dias)"
  type        = number
  default     = 15
}
