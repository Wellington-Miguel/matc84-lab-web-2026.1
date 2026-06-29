CREATE SCHEMA IF NOT EXISTS "auth";

CREATE TABLE "auth"."users" (
    "id" TEXT NOT NULL,
    "cognito_sub" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "email" TEXT NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "users_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "users_cognito_sub_key" ON "auth"."users"("cognito_sub");
CREATE UNIQUE INDEX "users_email_key" ON "auth"."users"("email");
