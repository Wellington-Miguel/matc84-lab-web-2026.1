# Authentication Lambda

API NestJS para cadastro e autenticação com AWS Cognito. O perfil do usuário é
persistido em PostgreSQL por Prisma ORM; senhas e tokens não são gravados no
banco.

O Prisma fica em `/lambdas/@libs/prisma` para poder ser reaproveitado por
outras Lambdas. O banco é único e usa PostgreSQL multi-schema: este domínio
grava no schema `auth`, e novos domínios devem adicionar seus modelos no mesmo
`schema.prisma` com `@@schema("<dominio>")`.

## Configuração

```bash
cp .env.example .env
npm install
npm run prisma:generate
npm run prisma:migrate:dev
npm run start:dev
```

Todas as configurações da aplicação estão em variáveis de ambiente, descritas
em `.env.example`. Credenciais AWS usam a cadeia padrão do AWS SDK (IAM Role na
Lambda ou perfil local).

`DATABASE_URL` deve apontar para o banco compartilhado, sem fixar `schema=...`
na URL. A separação por domínio é definida no Prisma por `schemas = [...]` e
`@@schema(...)`.

Para LocalStack, defina `AWS_ENDPOINT_URL=http://localhost:4566`. Se o endpoint
retornar `501 InternalFailure` para `cognito-idp`, o problema está no suporte do
LocalStack usado naquele ambiente; atualize/habilite Cognito no LocalStack ou
use AWS Cognito real para esse fluxo.

Swagger:

- Interface: `GET /docs`
- OpenAPI JSON: `GET /docs-json`

As rotas só existem quando `SWAGGER_ENABLED=true`.

## Rotas

- `POST /auth/register` — cria o usuário no Cognito e o perfil no PostgreSQL.
- `POST /auth/confirm` — confirma o código enviado por e-mail.
- `POST /auth/admin/confirm` — confirma manualmente no Cognito usando
  `x-admin-secret`; use apenas em desenvolvimento/administração.
- `POST /auth/login` — retorna os tokens do Cognito.
- `POST /auth/refresh` — renova access token e ID token.
- `POST /auth/validate-token` — recebe um access token e retorna
  `{ "valid": true | false }`.

Se o Cognito criar o usuário e o PostgreSQL continuar indisponível após os
retries com backoff exponencial e full jitter, a API publica um evento
sanitizado na fila definida por `AUTH_REGISTRATION_DLQ_URL` e retorna `201` com
`profileSync: "queued"`. A mensagem nunca contém senha ou tokens.

## Deploy e infraestrutura necessários

O artefato da Lambda deve usar runtime Node.js e handler `dist/lambda.handler`.
O build também copia o Prisma Client gerado da lib compartilhada para
`dist/@libs/prisma/generated` e cria wrappers `dist/main.js`/`dist/lambda.js`
para manter compatibilidade com o Nest CLI.
Antes do deploy:

- executar `npm run prisma:migrate:deploy` contra o PostgreSQL;
- adicionar ao API Gateway as rotas públicas `/auth/register`,
  `/auth/confirm`, `/auth/login` e `/auth/refresh`;
- habilitar `ALLOW_USER_PASSWORD_AUTH` e `ALLOW_REFRESH_TOKEN_AUTH` no Cognito
  App Client;
- criar uma SQS exclusiva para falhas de cadastro e definir sua URL em
  `AUTH_REGISTRATION_DLQ_URL`;
- conceder à Lambda `sqs:SendMessage` somente nessa fila;
- se usar `/auth/admin/confirm`, conceder `cognito-idp:AdminConfirmSignUp`
  para o User Pool e configurar `AUTH_ADMIN_CONFIRM_*`;
- fornecer conectividade de rede entre Lambda e PostgreSQL;
- publicar `/docs` e `/docs-json` no API Gateway apenas quando o Swagger for
  habilitado.

O Terraform atual do repositório ainda espera Java 21/SnapStart e utiliza
`COGNITO_POOL_ID`; ele precisa ser ajustado externamente para Node.js e
`COGNITO_USER_POOL_ID`.

## Verificação

```bash
npm test
npm run test:e2e
npm run lint
npm run build
```
