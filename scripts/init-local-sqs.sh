#!/bin/sh
set -eu

cd "$(dirname "$0")/../lambdas/pedidos/src"
node scripts/init-local-sqs.cjs
