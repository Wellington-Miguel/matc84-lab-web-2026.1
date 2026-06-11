# =============================================================================
# Módulo canônico de workload Lambda
# Toda Lambda do projeto é instanciada a partir deste módulo — alterações
# aqui refletem em todas as funções (auth, pedidos, produtos, pagamentos).
# =============================================================================

variable "function_name" {
  description = "Nome completo da função (ex: distribuicao-bebidas-dev-auth)"
  type        = string
}

variable "handler" {
  description = "Handler da Lambda (convenção: com.<projeto>.<modulo>.Handler::handleRequest)"
  type        = string
}

variable "runtime" {
  description = "Runtime da Lambda"
  type        = string
  default     = "java21"
}

variable "memory_size" {
  description = "Memória alocada (MB)"
  type        = number
  default     = 512
}

variable "timeout" {
  description = "Timeout (segundos)"
  type        = number
  default     = 30
}

variable "filename" {
  description = "Caminho do zip placeholder usado apenas no apply inicial (código real via CI/CD)"
  type        = string
}

variable "subnet_ids" {
  description = "Subnets privadas onde a Lambda executa"
  type        = list(string)
}

variable "security_group_ids" {
  description = "Security groups da Lambda"
  type        = list(string)
}

variable "environment_variables" {
  description = "Variáveis de ambiente da função"
  type        = map(string)
  default     = {}
}

variable "log_retention_days" {
  description = "Retenção do log group CloudWatch (dias)"
  type        = number
  default     = 15
}

variable "policy_statements" {
  description = "Statements IAM específicos deste workload (além da política base de logs/VPC)"
  type = list(object({
    sid       = string
    effect    = optional(string, "Allow")
    actions   = list(string)
    resources = list(string)
  }))
  default = []
}
