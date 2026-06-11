# Terraform — Distribuidora de Bebidas

Infraestrutura AWS serverless-first provisionada com Terraform, organizada em
módulos com um **módulo canônico** (`modules/stack`) instanciado por ambiente
(`envs/dev` e `envs/prod`).

## Arquitetura

```
Actor → API Gateway (HTTP API) → Lambda auth       → OpenSearch (sessões/busca)
                               → Lambda pedidos    → DynamoDB + SQS
                               → Lambda produtos   ← SQS (consumer)
                               → Lambda pagamentos → DynamoDB + SQS

Cognito JWT Authorizer — todas as rotas exceto /auth/*
```

## Recursos provisionados

| Recurso | Tipo | Finalidade |
|---|---|---|
| VPC | /16 com 2 AZs | Isolamento de rede |
| API Gateway | HTTP API v2 | Entry point REST |
| Lambda auth | Java 21 + SnapStart | Validação JWT + OpenSearch |
| Lambda pedidos | Java 21 + SnapStart | CRUD DynamoDB + SQS publish |
| Lambda produtos | Java 21 + SnapStart | Catálogo + SQS consumer |
| Lambda pagamentos | Java 21 + SnapStart | Transações financeiras |
| Cognito | User Pool | Identity provider |
| OpenSearch | Single-node VPC | Busca de sessões/catálogo |
| DynamoDB | 2 tabelas PAY_PER_REQUEST | pedidos + produtos |
| SQS | Fila + DLQ | Desacoplamento async |

## Estrutura de pastas

```
terraform-distribuicao/
├── modules/
│   ├── stack/         # MÓDULO CANÔNICO — compõe toda a infra;
│   │                  # alterações aqui refletem em todos os ambientes
│   ├── lambda/        # Módulo canônico de Lambda (main, iam, cloudwatch, outputs)
│   ├── cloudwatch/    # Observabilidade global: tópico SNS de alarmes + dashboard
│   ├── vpc/           # VPC, subnets, NAT, security groups
│   ├── api-gateway/   # HTTP API + authorizer Cognito + rotas + access logs
│   ├── cognito/       # Cognito User Pool + App Client
│   ├── dynamodb/      # Tabelas DynamoDB (pedidos, produtos)
│   ├── sqs/           # SQS + DLQ + alarmes CloudWatch
│   └── opensearch/    # OpenSearch + slow logs
├── envs/
│   ├── dev/           # providers.tf, variables.tf, main.tf, outputs.tf
│   └── prod/          # idem — instancia modules/stack com environment = "prod"
└── placeholder/       # Bootstrap inicial das Lambdas (zip gerado em runtime)
```

As pastas dos módulos usam o nome do serviço AWS correspondente. O módulo
`cloudwatch` centraliza a observabilidade do projeto: um tópico SNS único para
onde todos os alarmes apontam (`alarm_actions`) e um dashboard agregando as
métricas de SQS e Lambda. Defina `alarm_email` no ambiente para receber as
notificações por e-mail.

Cada workload Lambda (auth, pedidos, produtos, pagamentos) é uma instância do
módulo `lambda`, que padroniza: log group CloudWatch com
`retention_in_days = 15` (estratégia de expiração de logs), IAM role com
política base (logs + VPC) + statements específicos por parâmetro, SnapStart,
alias `live` e VPC config.

## Pré-requisitos

```bash
# Terraform >= 1.7
terraform -version

# AWS CLI configurado
aws sts get-caller-identity

# Java 21 + Maven/Gradle para os JARs
java -version
```

## Primeiro deploy

```bash
# Escolha o ambiente
cd envs/dev   # ou envs/prod

# 1. Inicializar providers
terraform init

# 2. Revisar o plano — NUNCA aplique sem ler o plan
terraform plan -out=tfplan

# 3. Aplicar
terraform apply tfplan

# 4. Ver outputs
terraform output
```

## CI/CD

O workflow `.github/workflows/infra.yml` (raiz do repositório) executa:

1. **validate** — `terraform fmt -check` + `terraform validate` para dev e prod
   em todo PR/push que toque a infra.
2. **infra-dev** — `plan` + `apply` automático em `envs/dev` após merge na `main`.
3. **infra-prod** — roda somente depois do dev; usa o GitHub Environment
   `infra-prod`, onde se configura **required reviewers** para aprovação manual.

Configure em *Settings → Environments* os ambientes `infra-dev` e `infra-prod`,
cada um com o secret `AWS_ROLE_ARN` (role IAM com trust via OIDC do GitHub).

## Deploy de código Lambda (pós-primeiro apply)

O módulo `lambda-workload` usa `lifecycle { ignore_changes = [filename] }` —
o código é gerenciado pelo CI/CD:

```bash
# Gerar o JAR fat/shadow com seu build tool
./gradlew shadowJar

# Atualizar a função (substitua <ambiente> por dev|prod e <modulo> por auth|pedidos|produtos|pagamentos)
aws lambda update-function-code \
  --function-name distribuicao-bebidas-<ambiente>-<modulo> \
  --zip-file fileb://build/libs/<modulo>-all.jar \
  --region us-east-1

# Publicar nova versão (necessário para SnapStart)
aws lambda publish-version \
  --function-name distribuicao-bebidas-<ambiente>-<modulo>

# Atualizar alias "live" para a nova versão
aws lambda update-alias \
  --function-name distribuicao-bebidas-<ambiente>-<modulo> \
  --name live \
  --function-version <numero-da-versao>
```

## Ativar backend S3 (recomendado para times)

1. Criar o bucket e a tabela de lock:
```bash
aws s3api create-bucket \
  --bucket distribuicao-terraform-state \
  --region us-east-1

aws dynamodb create-table \
  --table-name terraform-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST
```

2. Descomentar o bloco `backend "s3"` em `envs/<ambiente>/providers.tf`
   (cada ambiente usa uma key própria: `dev/terraform.tfstate`, `prod/terraform.tfstate`)

3. Migrar state local:
```bash
terraform init -migrate-state
```

## Destruir (cuidado em produção)

```bash
cd envs/<ambiente>
terraform destroy
```
