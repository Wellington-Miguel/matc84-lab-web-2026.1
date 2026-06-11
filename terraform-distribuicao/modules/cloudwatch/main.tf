# =============================================================================
# Tópico SNS de alarmes — destino único de todos os alarmes do projeto.
# Os módulos (sqs, etc.) recebem este ARN e o usam em alarm_actions/ok_actions.
# =============================================================================
resource "aws_sns_topic" "alarms" {
  name = "${var.prefix}-alarms"
  tags = { Name = "${var.prefix}-alarms" }
}

# Inscrição opcional por e-mail (confirmar via link enviado pela AWS)
resource "aws_sns_topic_subscription" "email" {
  count = var.alarm_email != "" ? 1 : 0

  topic_arn = aws_sns_topic.alarms.arn
  protocol  = "email"
  endpoint  = var.alarm_email
}

# =============================================================================
# Dashboard único do projeto — agrega SQS, Lambda e OpenSearch.
# Nomes dos recursos são derivados do prefixo (determinísticos), por isso o
# dashboard não depende dos demais módulos e não cria ciclo com os alarmes.
# =============================================================================
locals {
  queue_name = "${var.prefix}-pedidos"
  dlq_name   = "${var.prefix}-pedidos-dlq"

  # Métricas de Lambda: uma série de Invocations/Errors/Duration por função
  lambda_invocation_metrics = [
    for n in var.lambda_names :
    ["AWS/Lambda", "Invocations", "FunctionName", "${var.prefix}-${n}", { stat = "Sum", label = n }]
  ]
  lambda_error_metrics = [
    for n in var.lambda_names :
    ["AWS/Lambda", "Errors", "FunctionName", "${var.prefix}-${n}", { stat = "Sum", label = n }]
  ]
}

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.prefix}-overview"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title   = "SQS — mensagens na fila e na DLQ"
          region  = var.aws_region
          view    = "timeSeries"
          stacked = false
          metrics = [
            ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", local.queue_name, { stat = "Maximum", label = "fila" }],
            ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", local.dlq_name, { stat = "Maximum", label = "DLQ" }],
          ]
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "SQS — idade da mensagem mais antiga (s)"
          region = var.aws_region
          view   = "timeSeries"
          metrics = [
            ["AWS/SQS", "ApproximateAgeOfOldestMessage", "QueueName", local.queue_name, { stat = "Maximum" }],
          ]
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          title   = "Lambda — invocações"
          region  = var.aws_region
          view    = "timeSeries"
          stacked = false
          metrics = local.lambda_invocation_metrics
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        properties = {
          title   = "Lambda — erros"
          region  = var.aws_region
          view    = "timeSeries"
          stacked = false
          metrics = local.lambda_error_metrics
        }
      },
    ]
  })
}
