# MATC84 - Laboratório de Programação Web

Bem-vindo ao repositório oficial da disciplina **MATC84 - Laboratório de Programação Web**. Este espaço foi criado para acompanhar o desenvolvimento dos projetos práticos da nossa turma ao longo do semestre.

---

## 🌿 Equipe 01 - Projeto Distribuidora de Bebidas

Esta branch (`equipe-01-statelessness-e-estado-distribuido`) abriga a implementação do backend da **Distribuidora de Bebidas**, focado no pilar de **Statelessness e Estado Distribuído**.

### 👥 Integrantes
* **Lucca Giovanni Lobo Gonçalves** (Luccacalu)
* **Samuel de Almeida dos Santos** (samucaasantos)
* **Uanderson Santos Celestino** (wanderson-santo)
* **Mateus Chaves Moura** (matemoura)

### 🏗️ Arquitetura do Projeto

O serviço é um backend de alta performance construído em **Node.js com TypeScript e Fastify** que processa vendas concorrentes com garantias rígidas de integridade e resiliência:

1. **Estado Distribuído (PostgreSQL & DynamoDB):** 
   - O **PostgreSQL** gerencia o estado relacional persistente (estoque e fila de outbox).
   - O **DynamoDB** atua como uma camada rápida de cache distribuído de idempotência (fast-path).
2. **Garantia de Idempotência (Outbox Pattern):**
   - Cada requisição exige uma chave única no cabeçalho (`x-idempotency-key`).
   - Se a requisição cair no cache do DynamoDB, o processamento é evitado.
   - Em caso de falhas de rede com o DynamoDB, o [IdempotencyWorker.ts](distribuidora-bebidas/src/shared/services/IdempotencyWorker.ts) sincroniza o estado entre PostgreSQL e DynamoDB em background.
3. **Resolução de Concorrência Otimista (OCC):**
   - Para manter o servidor totalmente stateless, as colisões de concorrência são resolvidas no banco através de uma coluna version. Cada transação valida se a versão recebida ainda é a mesma antes de decrementar o estoque, retornando 422 se houver colisão.
4. **Política de Timeout Integrada:**
   - A camada de controle (`SalesController.ts`) implementa uma política de resiliência com tempo máximo de execução de **5 segundos (5000ms)** por requisição. Se o processamento estourar esse limite, a operação é abortada com status `504 Request Timeout`.
5. **Privacidade e Governança de Dados (LGPD):**
   - Toda a infraestrutura declarada no Terraform está rigidamente alocada na região de **São Paulo (`sa-east-1`)**. Como o sistema lida com dados de cidadãos brasileiros, o armazenamento local impede a evasão de dados para data centers internacionais (ex: Virgínia), garantindo conformidade com a LGPD.
6. **Desligamento Gracioso (Graceful Shutdown):**
   - O servidor intercepta sinais de desligamento (`SIGINT`/`SIGTERM`) para parar os workers em background e liberar conexões pendentes de banco.

---

## 🛠️ Tecnologias Utilizadas
* **Backend:** Node.js (v22.x+) & Fastify (v5.x)
* **Linguagem:** TypeScript
* **Bancos de Dados:** PostgreSQL 16 & DynamoDB (SDK v3)
* **Infraestrutura:** Docker, Docker Compose & Terraform
* **Testes:** Vitest (Suíte de Testes) & Autocannon (Benchmarking/Estresse)

---
# 🚀 Como Iniciar o Projeto

A aplicação e seus bancos de dados estão totalmente orquestrados via **Docker Compose**.

Navegue até a pasta do projeto:

```bash
cd distribuidora-bebidas
```

## 1. Subir a Infraestrutura (Docker)

Inicie os contêineres do banco relacional, banco NoSQL e a construção da imagem do backend:

```bash
docker compose up -d
```

---

## 2. Configurar o Banco de Dados Relacional (PostgreSQL)

Execute o script de setup por dentro da rede do contêiner. O script criará as tabelas, inserirá um produto de teste e gerará automaticamente o arquivo `.env` na raiz do projeto.

```bash
docker compose run --rm backend node tests/setup-db.js
```

### Credenciais solicitadas pelo script

| Campo | Valor |
|--------|--------|
| **Usuário** | `postgres` |
| **Senha** | `password` |
| **Host** | `postgres` |
| **Porta** | `5432` |

> **⚠️ Atenção:** Guarde o **UUID (`productId`)** gerado no terminal ao final deste processo.

---

## 3. Configurar a Camada NoSQL (DynamoDB Local)

Crie a tabela de idempotência dentro do emulador utilizando o endpoint dinâmico da rede interna:

```bash
docker compose run --rm backend node tests/setup-dynamo.js
```

---

## 4. Iniciar o Servidor

Com os bancos populados, reinicie o backend para que ele aplique as configurações e os volumes compilados (`/dist`):

```bash
docker compose up -d --force-recreate backend
```

Acompanhe a integridade da aplicação pelos logs:

```bash
docker compose logs -f backend
```

O servidor estará acessível em:

```text
http://localhost:3000
```

---

# 💻 Execução Local Híbrida (Modo Desenvolvedor)

Caso prefira rodar a aplicação nativamente no terminal (mantendo apenas os bancos no Docker), modifique o arquivo `.env` gerado.

Altere os hosts internos do Docker (`postgres`) para `localhost`:

```env
DATABASE_URL=postgresql://postgres:password@localhost:5432/salesdb
DYNAMO_ENDPOINT=http://localhost:8123
```

Instale as dependências locais:

```bash
npm install
```

Inicie o servidor:

```bash
npm run dev
```

---

# 🔍 Rotas de Inspeção e Debug Local

Para facilitar a validação do estado do sistema em tempo real:

### Listagem de Estoque

```http
GET http://localhost:3000/v1/products
```

Retorna o estado atualizado do produto e os incrementos da coluna `version`.

### Histórico de Idempotência

```http
GET http://localhost:3000/v1/idempotency
```

Retorna os últimos 50 registros salvos na tabela `idempotency_outbox` do PostgreSQL para acompanhar a sincronização assíncrona.

---

# 🧪 Rodando Testes Automatizados

O projeto conta com testes unitários e de integração.

Para executar toda a suíte via Vitest:

```bash
npm test
```

## 🧪 Suíte de Testes e Validação Real

A aplicação divide sua estratégia de testes em duas camadas fundamentais:

1. **Testes Unitários e de Contrato (`tests/unit` e `tests/integration`)**
   - Utilizam dublês de teste (*mocks*) para validar caminhos de decisão isolados em alta velocidade.

2. **Teste de Concorrência Real (`tests/sales-concurrency.spec.ts`)**
   - Simula um cenário extremo disparando **10 requisições paralelas simultâneas** contra o mesmo item.
   - Valida na prática o **Controle de Concorrência Otimista (OCC)**.
   - Permite apenas **1 venda** com sucesso (`201`).
   - Rejeita as demais por conflito de versão (`422`).

---

# 📈 Testes de Estresse e Concorrência (Autocannon)

Para simular **100 conexões simultâneas** enviando vendas concorrentes durante **30 segundos**, utilize o script de benchmark:

```bash
node tests/benchmark.js <UUID_DO_PRODUTO>
```
