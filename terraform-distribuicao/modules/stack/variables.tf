# =============================================================================
# Módulo canônico (stack) — define como toda a infraestrutura é criada.
# Os ambientes (envs/dev, envs/prod) apenas instanciam este módulo com
# parâmetros próprios; alterações aqui refletem em todos os ambientes.
# =============================================================================

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

variable "environment" {
  description = "Ambiente de deploy (prod, staging, dev)"
  type        = string

  validation {
    condition     = contains(["prod", "staging", "dev"], var.environment)
    error_message = "environment deve ser prod, staging ou dev."
  }
}

# --- VPC ---
variable "vpc_cidr" {
  description = "CIDR block da VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "private_subnet_cidrs" {
  description = "CIDRs das subnets privadas (mínimo 2 AZs)"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "public_subnet_cidrs" {
  description = "CIDRs das subnets públicas"
  type        = list(string)
  default     = ["10.0.101.0/24", "10.0.102.0/24"]
}

# --- Lambda ---
variable "lambda_runtime" {
  description = "Runtime das Lambdas"
  type        = string
  default     = "java21"
}

variable "lambda_memory_mb" {
  description = "Memória alocada para cada Lambda (MB)"
  type        = number
  default     = 512
}

variable "lambda_timeout_s" {
  description = "Timeout das Lambdas (segundos)"
  type        = number
  default     = 30
}

# --- OpenSearch ---
variable "opensearch_instance_type" {
  description = "Tipo de instância do OpenSearch"
  type        = string
  default     = "t3.small.search"
}

variable "opensearch_volume_gb" {
  description = "Tamanho do volume EBS do OpenSearch (GB)"
  type        = number
  default     = 20
}

# --- SQS ---
variable "sqs_visibility_timeout_s" {
  description = <<-EOT
    Visibility timeout da fila SQS em segundos.
    REGRA: deve ser >= timeout da Lambda consumidora.
    Default: 120s (4× o timeout padrão de 30s das Lambdas — margem de segurança).
  EOT
  type        = number
  default     = 120
}

variable "sqs_message_retention_days" {
  description = "Retenção de mensagens na fila principal (dias). Padrão AWS: 4. Máximo: 14."
  type        = number
  default     = 4

  validation {
    condition     = var.sqs_message_retention_days >= 1 && var.sqs_message_retention_days <= 14
    error_message = "sqs_message_retention_days deve estar entre 1 e 14."
  }
}

variable "sqs_max_receive_count" {
  description = "Tentativas de processamento antes de mover para DLQ"
  type        = number
  default     = 3
}

# --- Logs ---
variable "log_retention_days" {
  description = "Retenção de logs CloudWatch (dias) — estratégia de expiração padrão: 15 dias"
  type        = number
  default     = 15
}
