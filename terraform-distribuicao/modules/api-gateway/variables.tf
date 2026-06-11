variable "prefix" {
  description = "Prefixo de nomes dos recursos (projeto-ambiente)"
  type        = string
}

variable "stage_name" {
  description = "Nome do stage do API Gateway (normalmente o ambiente: dev/prod)"
  type        = string
}

variable "cognito_client_id" {
  description = "Audience do authorizer JWT (Client ID do Cognito App Client)"
  type        = string
}

variable "cognito_issuer_url" {
  description = "Issuer URL do Cognito User Pool"
  type        = string
}

variable "log_retention_days" {
  description = "Retenção dos access logs no CloudWatch (dias)"
  type        = number
  default     = 15
}

variable "lambda_integrations" {
  description = "Workloads Lambda integrados ao API Gateway, indexados pelo nome lógico (auth, pedidos, produtos, pagamentos)"
  type = map(object({
    function_name    = string
    alias_name       = string
    alias_invoke_arn = string
  }))
}
