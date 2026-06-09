#!/bin/bash
# infra/localstack/setup-queues.sh
# Executado automaticamente pelo LocalStack ao iniciar

echo "Criando filas SQS no LocalStack..."

awslocal sqs create-queue \
  --queue-name bebidas-orders.fifo \
  --attributes FifoQueue=true,ContentBasedDeduplication=true

awslocal sqs create-queue \
  --queue-name bebidas-orders-dlq.fifo \
  --attributes FifoQueue=true

awslocal sqs create-queue \
  --queue-name bebidas-payments.fifo \
  --attributes FifoQueue=true,ContentBasedDeduplication=true

awslocal sqs create-queue \
  --queue-name bebidas-inventory

echo "Filas criadas com sucesso!"
awslocal sqs list-queues
