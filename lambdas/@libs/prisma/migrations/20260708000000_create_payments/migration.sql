CREATE SCHEMA IF NOT EXISTS "pagamentos";

CREATE TABLE "pagamentos"."payments" (
  "id" TEXT NOT NULL,
  "payment_attempt_id" TEXT NOT NULL,
  "order_id" TEXT NOT NULL,
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT "payments_pkey" PRIMARY KEY ("id")
);

CREATE INDEX "payments_payment_attempt_id_idx" ON "pagamentos"."payments"("payment_attempt_id");
CREATE INDEX "payments_order_id_idx" ON "pagamentos"."payments"("order_id");
