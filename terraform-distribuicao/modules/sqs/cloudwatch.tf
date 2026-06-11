# =============================================================================
# Alarme CloudWatch
# Qualquer mensagem na DLQ indica falha persistente (esgotou os retries).
# Dispara imediatamente — não espera 5 minutos como alarmes de média.
# =============================================================================
resource "aws_cloudwatch_metric_alarm" "pedidos_dlq_not_empty" {
  alarm_name          = "${var.prefix}-pedidos-dlq-not-empty"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"
  alarm_description   = "DLQ de pedidos não está vazia — Lambda produtos falhou ${var.max_receive_count}× seguidas"

  alarm_actions = var.alarm_actions
  ok_actions    = var.alarm_actions

  dimensions = {
    QueueName = aws_sqs_queue.pedidos_dlq.name
  }

  tags = { Name = "${var.prefix}-dlq-alarm" }
}

# =============================================================================
# Alarme: age das mensagens na fila principal
# Se mensagens ficam > 1h sem processamento, algo está errado com a consumidora.
# =============================================================================
resource "aws_cloudwatch_metric_alarm" "pedidos_age" {
  alarm_name          = "${var.prefix}-pedidos-message-age-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "ApproximateAgeOfOldestMessage"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Maximum"
  threshold           = 3600 # 1 hora
  treat_missing_data  = "notBreaching"
  alarm_description   = "Mensagem mais antiga da fila > 1h — verificar Lambda produtos (consumidora SQS)"

  alarm_actions = var.alarm_actions
  ok_actions    = var.alarm_actions

  dimensions = {
    QueueName = aws_sqs_queue.pedidos.name
  }

  tags = { Name = "${var.prefix}-pedidos-age-alarm" }
}
