# =============================================================================
# Módulo CloudWatch global — observabilidade centralizada do projeto.
# Concentra o tópico SNS para onde todos os alarmes apontam e um dashboard
# único agregando as métricas de SQS, Lambda e OpenSearch.
# =============================================================================

variable "prefix" {
  description = "Prefixo de nomes dos recursos (projeto-ambiente)"
  type        = string
}

variable "aws_region" {
  description = "Região AWS — usada para montar os widgets do dashboard"
  type        = string
}

variable "lambda_names" {
  description = "Sufixos lógicos das Lambdas (ex: auth, pedidos) — usados no dashboard"
  type        = list(string)
  default     = []
}

variable "alarm_email" {
  description = "E-mail para receber notificações de alarme (vazio = sem inscrição)"
  type        = string
  default     = ""
}
