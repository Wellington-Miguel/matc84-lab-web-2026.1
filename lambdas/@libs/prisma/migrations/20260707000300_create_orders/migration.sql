CREATE SCHEMA IF NOT EXISTS "pedidos";

CREATE TYPE "pedidos"."OrderStatus" AS ENUM (
  'pending',
  'cancelled',
  'paid',
  'completed'
);

CREATE TABLE "pedidos"."orders" (
  "id" TEXT NOT NULL,
  "client_id" TEXT NOT NULL,
  "status" "pedidos"."OrderStatus" NOT NULL DEFAULT 'pending',
  "products" JSONB NOT NULL,
  "total" DECIMAL(10,2) NOT NULL,
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMP(3) NOT NULL,

  CONSTRAINT "orders_pkey" PRIMARY KEY ("id")
);

CREATE INDEX "orders_client_id_idx" ON "pedidos"."orders"("client_id");
CREATE INDEX "orders_status_idx" ON "pedidos"."orders"("status");
