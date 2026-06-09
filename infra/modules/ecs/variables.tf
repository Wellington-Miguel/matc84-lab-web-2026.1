variable "project_name" {
  description = "Nome do projeto"
  type        = string
}

variable "alb_target_group_arn" {
  description = "ARN do Target Group do ALB"
  type        = string
}

variable "db_connection_string_secret_arn" {
  description = "ARN do segredo contendo a URL de conexão completa do banco"
  type        = string
}

variable "sqs_order_queue_url" {
  description = "URL da fila SQS de pedidos"
  type        = string
}