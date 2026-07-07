#!/bin/bash
# infra/localstack/setup-queues.sh
# Setup das filas SQS no LocalStack

set -e

echo "Aguardando LocalStack ficar pronto..."
sleep 5

# Variables
LOCALSTACK_ENDPOINT="http://localhost:4566"
REGION="us-east-1"

echo "Criando filas SQS no LocalStack..."

# Fila de pedidos (FIFO - First In First Out)
echo "Criando fila: bebidas-orders.fifo"
awslocal sqs create-queue \
  --queue-name bebidas-orders.fifo \
  --region $REGION \
  --attributes FifoQueue=true,ContentBasedDeduplication=true || true

# Fila de notificações (FIFO)
echo "Criando fila: notifications.fifo"
awslocal sqs create-queue \
  --queue-name notifications.fifo \
  --region $REGION \
  --attributes FifoQueue=true,ContentBasedDeduplication=true || true

# Fila DLQ (Dead Letter Queue) para erros
echo "Criando fila: bebidas-orders-dlq.fifo"
awslocal sqs create-queue \
  --queue-name bebidas-orders-dlq.fifo \
  --region $REGION \
  --attributes FifoQueue=true || true

echo "Listando filas criadas:"
awslocal sqs list-queues --region $REGION

echo "Setup das filas concluído!"
