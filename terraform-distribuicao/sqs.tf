# =============================================================================
# Arquitetura SQS
#
# Frontend → API Gateway → Lambda (produtora) → SQS → Lambda (consumidora) → DynamoDB
#
# Fluxo de operações por mensagem:
#   1. SendMessage   — Lambda pedidos/pagamentos envia evento para a fila
#   2. ReceiveMessage — Lambda produtos consome (mensagem fica invisível)
#   3. DeleteMessage  — Lambda produtos remove após processamento bem-sucedido
#
# Custo estimado (180k eventos/mês):
#   540k operações/mês (3 ops × 180k)
#   Free Tier AWS SQS: 1M requisições/mês gratuitas
#   540k < 1M → dentro do Free Tier → US$ 0,00
#   Após Free Tier: US$ 0,40/M req → 540k = ~US$ 0,22/mês
# =============================================================================

# =============================================================================
# Dead-Letter Queue
# Recebe mensagens após `sqs_max_receive_count` tentativas frustradas.
# Retenção máxima de 14 dias — janela para análise de falhas sem perda de dados.
# =============================================================================
resource "aws_sqs_queue" "pedidos_dlq" {
  name                      = "${local.prefix}-pedidos-dlq"
  message_retention_seconds = 1209600 # 14 dias — máximo permitido pelo SQS

  sqs_managed_sse_enabled = true

  tags = { Name = "${local.prefix}-pedidos-dlq" }
}

# =============================================================================
# Fila principal: pedidos
#
# Produtoras : Lambda pedidos, Lambda pagamentos  (SendMessage)
# Consumidora: Lambda produtos                     (ReceiveMessage + DeleteMessage)
#
# Visibility Timeout
# ─────────────────
# Ao chamar ReceiveMessage, a mensagem desaparece da fila pelo período definido.
# Se a Lambda consumidora falhar antes de DeleteMessage (crash, timeout, erro),
# a mensagem retorna automaticamente sem intervenção — tolerância a falhas nativa.
# Regra: visibility_timeout >= timeout da Lambda consumidora.
# Default aqui: 120s (4× o timeout de 30s — margem para retries internos do JVM).
#
# Retenção
# ────────
# Padrão AWS: 4 dias. Configurável via var.sqs_message_retention_days (1–14 dias).
# DLQ mantém 14 dias para permitir análise forense de falhas persistentes.
# =============================================================================
resource "aws_sqs_queue" "pedidos" {
  name = "${local.prefix}-pedidos"

  # Visibility Timeout: mensagem fica invisível enquanto está sendo processada
  visibility_timeout_seconds = var.sqs_visibility_timeout_s

  # Retenção: padrão 4 dias (345600s), ajustável via variável
  message_retention_seconds = var.sqs_message_retention_days * 86400

  delay_seconds    = 0       # sem atraso de entrega
  max_message_size = 262144  # 256 KB — máximo SQS

  # Redrive: após maxReceiveCount falhas → DLQ
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.pedidos_dlq.arn
    maxReceiveCount     = var.sqs_max_receive_count
  })

  sqs_managed_sse_enabled = true

  tags = { Name = "${local.prefix}-pedidos" }
}

# =============================================================================
# Alarme CloudWatch
# Qualquer mensagem na DLQ indica falha persistente (esgotou os 3 retries).
# Dispara imediatamente — não espera 5 minutos como alarmes de média.
# =============================================================================
resource "aws_cloudwatch_metric_alarm" "pedidos_dlq_not_empty" {
  alarm_name          = "${local.prefix}-pedidos-dlq-not-empty"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"
  alarm_description   = "DLQ de pedidos não está vazia — Lambda produtos falhou ${var.sqs_max_receive_count}× seguidas"

  dimensions = {
    QueueName = aws_sqs_queue.pedidos_dlq.name
  }

  tags = { Name = "${local.prefix}-dlq-alarm" }
}

# =============================================================================
# Alarme: age das mensagens na fila principal
# Se mensagens ficam > 1h sem processamento, algo está errado com a consumidora.
# =============================================================================
resource "aws_cloudwatch_metric_alarm" "pedidos_age" {
  alarm_name          = "${local.prefix}-pedidos-message-age-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "ApproximateAgeOfOldestMessage"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Maximum"
  threshold           = 3600 # 1 hora
  treat_missing_data  = "notBreaching"
  alarm_description   = "Mensagem mais antiga da fila > 1h — verificar Lambda produtos (consumidora SQS)"

  dimensions = {
    QueueName = aws_sqs_queue.pedidos.name
  }

  tags = { Name = "${local.prefix}-pedidos-age-alarm" }
}
