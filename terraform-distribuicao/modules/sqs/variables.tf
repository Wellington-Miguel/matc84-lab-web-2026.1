variable "prefix" {
  description = "Prefixo de nomes dos recursos (projeto-ambiente)"
  type        = string
}

variable "visibility_timeout_s" {
  description = <<-EOT
    Visibility timeout da fila SQS em segundos.
    REGRA: deve ser >= timeout da Lambda consumidora.
    Durante esse período a mensagem fica invisível para outros consumidores.
    Se a Lambda falhar antes de DeleteMessage, a mensagem retorna automaticamente.
  EOT
  type        = number
  default     = 120
}

variable "message_retention_days" {
  description = "Retenção de mensagens na fila principal (dias). Padrão AWS: 4. Máximo: 14."
  type        = number
  default     = 4

  validation {
    condition     = var.message_retention_days >= 1 && var.message_retention_days <= 14
    error_message = "message_retention_days deve estar entre 1 e 14."
  }
}

variable "max_receive_count" {
  description = "Tentativas de processamento antes de mover para DLQ"
  type        = number
  default     = 3
}

variable "alarm_actions" {
  description = "ARNs notificados quando os alarmes disparam (ex: tópico SNS global do módulo cloudwatch)"
  type        = list(string)
  default     = []
}
