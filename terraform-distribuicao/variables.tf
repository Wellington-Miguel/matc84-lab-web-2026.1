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
  default     = "prod"

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

# --- Aurora Serverless v2 ---
variable "aurora_min_capacity" {
  description = "Capacidade mínima Aurora Serverless v2 (ACU)"
  type        = number
  default     = 0.5
}

variable "aurora_max_capacity" {
  description = "Capacidade máxima Aurora Serverless v2 (ACU)"
  type        = number
  default     = 4
}

variable "aurora_engine_version" {
  description = "Versão do engine PostgreSQL no Aurora"
  type        = string
  default     = "16.1"
}

variable "aurora_database_name" {
  description = "Nome do banco de dados inicial"
  type        = string
  default     = "distribuicao"
}

# --- SQS ---
variable "sqs_visibility_timeout_s" {
  description = <<-EOT
    Visibility timeout da fila SQS em segundos.
    REGRA: deve ser >= timeout da Lambda consumidora.
    Durante esse período a mensagem fica invisível para outros consumidores.
    Se a Lambda falhar antes de DeleteMessage, a mensagem retorna automaticamente.
    Default: 120s (2× o timeout padrão de 30s das Lambdas — margem de segurança).
  EOT
  type        = number
  default     = 120
}

variable "sqs_message_retention_days" {
  description = <<-EOT
    Retenção de mensagens na fila principal (dias).
    Padrão AWS: 4 dias. Máximo: 14 dias.
    Com 180k eventos/mês o custo estimado é ~US$ 0,22/mês após Free Tier
    (540k operações: SendMessage + ReceiveMessage + DeleteMessage por evento).
    O Free Tier cobre 1M requisições/mês — 540k/mês permanece dentro dele.
  EOT
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
  description = "Retenção de logs CloudWatch (dias)"
  type        = number
  default     = 30
}
