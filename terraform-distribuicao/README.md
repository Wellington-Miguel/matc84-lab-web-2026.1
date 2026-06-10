# Terraform — Distribuidora de Bebidas

Infraestrutura AWS serverless-first provisionada com Terraform.

## Arquitetura

```
Actor → API Gateway (HTTP API) → Lambda auth       → OpenSearch (sessões/busca)
                               → Lambda pedidos    → DynamoDB + SQS
                               → Lambda produtos   ← SQS (consumer)
                               → Lambda pagamentos → DynamoDB + SQS

Cognito JWT Authorizer — todas as rotas exceto /auth/*
Secrets Manager       — credenciais Aurora para as Lambdas
Aurora Serverless v2  — persistência relacional (relatórios, joins)
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
| Aurora Serverless v2 | PostgreSQL 16 | Relatórios + auditoria |
| Secrets Manager | 1 secret | Credenciais Aurora |

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
# 1. Inicializar providers
terraform init

# 2. Revisar o plano — NUNCA aplique sem ler o plan
terraform plan -out=tfplan

# 3. Aplicar
terraform apply tfplan

# 4. Ver outputs
terraform output
```

## Deploy de código Lambda (pós-primeiro apply)

O Terraform usa `lifecycle { ignore_changes = [filename] }` — o código é
gerenciado pelo CI/CD:

```bash
# Gerar o JAR fat/shadow com seu build tool
./gradlew shadowJar

# Atualizar a função (substitua <modulo> por auth|pedidos|produtos|pagamentos)
aws lambda update-function-code \
  --function-name distribuicao-bebidas-prod-<modulo> \
  --zip-file fileb://build/libs/<modulo>-all.jar \
  --region us-east-1

# Publicar nova versão (necessário para SnapStart)
aws lambda publish-version \
  --function-name distribuicao-bebidas-prod-<modulo>

# Atualizar alias "live" para a nova versão
aws lambda update-alias \
  --function-name distribuicao-bebidas-prod-<modulo> \
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

2. Descomentar o bloco `backend "s3"` em `providers.tf`

3. Migrar state local:
```bash
terraform init -migrate-state
```

## Destruir (cuidado em produção)

```bash
# Aurora tem deletion_protection = true — desabilite antes:
terraform apply -target=aws_rds_cluster.main \
  -var="..." # ajuste as variáveis se necessário

terraform destroy
```

## Estrutura de arquivos

```
terraform-distribuicao/
├── providers.tf      # AWS + random providers, backend S3
├── variables.tf      # Todas as variáveis de entrada
├── locals.tf         # Valores computados (prefixos, handlers)
├── outputs.tf        # URLs, ARNs, IDs exportados
├── vpc.tf            # VPC, subnets, NAT, SGs
├── cognito.tf        # User Pool + App Client
├── secrets.tf        # Secrets Manager (Aurora credentials)
├── dynamodb.tf       # Tabelas pedidos + produtos
├── sqs.tf            # Fila + DLQ + alarme CloudWatch
├── opensearch.tf     # Domínio OpenSearch + política de acesso
├── aurora.tf         # Cluster Serverless v2 + instância
├── iam.tf            # Roles + policies de cada Lambda
├── lambdas.tf        # 4 Lambdas + SnapStart + aliases + log groups
├── api_gateway.tf    # HTTP API + Cognito authorizer + rotas
└── placeholder.zip   # Bootstrap inicial (substituído pelo CI/CD)
```
