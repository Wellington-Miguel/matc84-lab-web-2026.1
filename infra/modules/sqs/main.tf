variable "project_name" {}
variable "environment"  {}

# ── Padrão: para cada domínio, criamos fila principal + DLQ ───────────────────

# ── Pedidos (FIFO — garante ordem) ───────────────────────────────────────────
resource "aws_sqs_queue" "orders_dlq" {
  name       = "${var.project_name}-orders-dlq.fifo"
  fifo_queue = true
  tags       = { Name = "orders-dlq" }
}

resource "aws_sqs_queue" "orders" {
  name                        = "${var.project_name}-orders.fifo"
  fifo_queue                  = true
  content_based_deduplication = true
  visibility_timeout_seconds  = 30   # tempo para o Lambda processar
  message_retention_seconds   = 86400  # 24h

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.orders_dlq.arn
    maxReceiveCount     = 5  # após 5 falhas → vai para DLQ
  })

  tags = { Name = "orders-queue" }
}

# ── Pagamentos (FIFO) ─────────────────────────────────────────────────────────
resource "aws_sqs_queue" "payments_dlq" {
  name       = "${var.project_name}-payments-dlq.fifo"
  fifo_queue = true
}

resource "aws_sqs_queue" "payments" {
  name                        = "${var.project_name}-payments.fifo"
  fifo_queue                  = true
  content_based_deduplication = true
  visibility_timeout_seconds  = 60

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.payments_dlq.arn
    maxReceiveCount     = 5
  })
}

# ── Estoque (Standard — alta throughput, ordem menos crítica) ─────────────────
resource "aws_sqs_queue" "inventory_dlq" {
  name = "${var.project_name}-inventory-dlq"
}

resource "aws_sqs_queue" "inventory" {
  name                       = "${var.project_name}-inventory"
  visibility_timeout_seconds = 30

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.inventory_dlq.arn
    maxReceiveCount     = 5
  })
}

output "order_queue_url"    { value = aws_sqs_queue.orders.url }
output "order_queue_arn"    { value = aws_sqs_queue.orders.arn }
output "payment_queue_url"  { value = aws_sqs_queue.payments.url }
output "inventory_queue_url"{ value = aws_sqs_queue.inventory.url }
