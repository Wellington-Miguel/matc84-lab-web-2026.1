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
# Recebe mensagens após `max_receive_count` tentativas frustradas.
# Retenção máxima de 14 dias — janela para análise de falhas sem perda de dados.
# =============================================================================
resource "aws_sqs_queue" "pedidos_dlq" {
  name                      = "${var.prefix}-pedidos-dlq"
  message_retention_seconds = 1209600 # 14 dias — máximo permitido pelo SQS

  sqs_managed_sse_enabled = true

  tags = { Name = "${var.prefix}-pedidos-dlq" }
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
#
# Retenção
# ────────
# Padrão AWS: 4 dias. Configurável via var.message_retention_days (1–14 dias).
# DLQ mantém 14 dias para permitir análise forense de falhas persistentes.
# =============================================================================
resource "aws_sqs_queue" "pedidos" {
  name = "${var.prefix}-pedidos"

  # Visibility Timeout: mensagem fica invisível enquanto está sendo processada
  visibility_timeout_seconds = var.visibility_timeout_s

  # Retenção: padrão 4 dias (345600s), ajustável via variável
  message_retention_seconds = var.message_retention_days * 86400

  delay_seconds    = 0      # sem atraso de entrega
  max_message_size = 262144 # 256 KB — máximo SQS

  # Redrive: após maxReceiveCount falhas → DLQ
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.pedidos_dlq.arn
    maxReceiveCount     = var.max_receive_count
  })

  sqs_managed_sse_enabled = true

  tags = { Name = "${var.prefix}-pedidos" }
}
