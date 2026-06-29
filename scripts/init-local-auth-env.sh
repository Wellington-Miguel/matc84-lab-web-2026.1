#!/bin/sh
set -eu

cd "$(dirname "$0")/../lambdas/auth/src/auth"
node scripts/init-local-env.cjs
