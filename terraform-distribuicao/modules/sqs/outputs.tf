output "queue_url" {
  description = "URL da fila SQS de pedidos"
  value       = aws_sqs_queue.pedidos.url
}

output "queue_arn" {
  description = "ARN da fila SQS de pedidos"
  value       = aws_sqs_queue.pedidos.arn
}

output "dlq_url" {
  description = "URL da Dead-Letter Queue"
  value       = aws_sqs_queue.pedidos_dlq.url
}

output "dlq_arn" {
  description = "ARN da Dead-Letter Queue"
  value       = aws_sqs_queue.pedidos_dlq.arn
}
