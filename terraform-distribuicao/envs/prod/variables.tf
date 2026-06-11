variable "aws_region" {
  description = "Região AWS para deploy"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Prefixo de nomes de todos os recursos"
  type        = string
  default     = "distribuicao-bebidas"
}

variable "log_retention_days" {
  description = "Retenção de logs CloudWatch (dias) — estratégia de expiração: 15 dias"
  type        = number
  default     = 15
}

variable "lambda_memory_mb" {
  description = "Memória alocada para cada Lambda (MB)"
  type        = number
  default     = 512
}

variable "opensearch_instance_type" {
  description = "Tipo de instância do OpenSearch"
  type        = string
  default     = "t3.small.search"
}

variable "alarm_email" {
  description = "E-mail inscrito no tópico SNS de alarmes (vazio = sem inscrição)"
  type        = string
  default     = ""
}
