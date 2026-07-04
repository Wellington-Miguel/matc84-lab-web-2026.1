# MATC84 - Laboratório de Programação Web

Bem-vindo ao repositório oficial da disciplina **MATC84 - Laboratório de Programação Web**. Este espaço foi criado para acompanhar o desenvolvimento dos projetos práticos da nossa turma ao longo do semestre.

---

## 🌿 Equipe 01 - Projeto Distribuidora de Bebidas

Esta branch (`equipe-01-statelessness-e-estado-distribuido`) abriga a implementação do backend da **Distribuidora de Bebidas**, focado no pilar de **Statelessness e Estado Distribuído**.

### 👥 Integrantes
* **Lucca Giovanni Lobo Gonçalves** (Luccacalu)
* **Samuel de Almeida dos Santos** (samucaasantos)

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

## 🚀 Como Iniciar o Projeto Localmente

Navegue até a pasta do projeto de bebidas e instale as dependências:
```bash
cd distribuidora-bebidas
npm install

```

### 1. Configurar o Banco de Dados Relacional (PostgreSQL)

Certifique-se de que o serviço do PostgreSQL está rodando nativamente na sua máquina (porta 5432). Execute o script interativo de setup automatizado:

```bash
node tests/setup-db.js

```

O script solicitará suas credenciais do Postgres e irá:

* Criar o banco de dados `salesdb`.
* Rodar as migrações (criar tabelas `products` e `idempotency_outbox`).
* Inserir um produto de teste com estoque de `10000` unidades e versão `1`.
* Gerar um arquivo `.env` configurado automaticamente.
* Guarde o UUID (productId) gerado pelo script no final da execução!

### 2. Opcional: Configurar a Camada NoSQL (DynamoDB Local)

Para emular o comportamento de nuvem da AWS localmente sem custos, o projeto utiliza um container Docker mapeado para a porta **8123**.

1. Certifique-se de que o **Docker Desktop** está aberto e rodando.
2. Inicie o container em background:
```bash
docker compose up -d

```


3. Execute o script de provisionamento para injetar as credenciais locais e criar a tabela de idempotência dentro do emulador:
```bash
node tests/setup-dynamo.js

```



### 3. Configurar as Variáveis de Ambiente

Verifique se o seu arquivo `.env` gerado na raiz do projeto possui as seguintes chaves preenchidas:

```env
PORT=3000
DATABASE_URL=postgres://SEU_USUARIO:SUA_SENHA@localhost:5432/salesdb
AWS_REGION=sa-east-1
DYNAMO_TABLE_NAME=sales-idempotency-dev # Mantenha vazia para não utilizar idempotency worker
DYNAMO_ENDPOINT=http://localhost:8123 # Essa linha apenas deve existir caso queira emular a AWS local/DynamoDB local
OUTBOX_WORKER_INTERVAL_MS=10000

```

> 💡 *Nota: Para rodar o projeto na AWS real de produção, basta apagar/remover a linha da variável `DYNAMO_ENDPOINT`.*

### 4. Rodar o Servidor

Execute o comando unificado de desenvolvimento (ele compila o TypeScript e inicializa o servidor automaticamente):

```bash
npm run dev

```

*O servidor estará escutando em `http://localhost:3000`.*
---

## 🔍 Rotas de Inspeção e Debug Local

Para facilitar a validação do estado do sistema em tempo real (especialmente durante demonstrações e apresentações), foram implementadas duas rotas auxiliares de inspeção visual:

* **Listagem de Estoque:** `GET http://localhost:3000/v1/products`
  * Retorna o estado atualizado do produto, permitindo checar o decremento do estoque e o incremento da `version` (Controle de Concorrência Otimista).
* **Histórico de Idempotência:** `GET http://localhost:3000/v1/idempotency`
  * Retorna os últimos 50 registros salvos na tabela `idempotency_outbox` do PostgreSQL, ideal para verificar o status de resiliência (`PROCESSING`, `COMPLETED` ou `FAILED`) e acompanhar a sincronização assíncrona feita pelo background worker.

---

## 🧪 Rodando Testes Automatizados

O projeto conta com testes unitários (para o fluxo de serviço) e de integração (validação de cabeçalhos, corpo e rotas HTTP em memória). Para rodar a suíte inteira via Vitest:

```bash
npm test

```

### 🧪 Suíte de Testes e Validação Real

A aplicação divide sua estratégia de testes em duas camadas fundamentais:

1. **Testes Unitários e de Contrato (`tests/unit` e `tests/integration`):** Utilizam dublês de teste (*mocks*) para validar caminhos de decisão isolados e validações de esquema das rotas HTTP em alta velocidade.
2. **Teste de Concorrência Real (`tests/sales-concurrency.spec.ts`):** Um teste de integração ponta a ponta que se conecta à infraestrutura local real (PostgreSQL). Ele simula um cenário extremo de concorrência disparando **10 requisições paralelas simultâneas** contra o mesmo item. O teste valida na prática se o mecanismo de **Controle de Concorrência Otimista (OCC)** do banco permite apenas 1 venda com sucesso (`201`), rejeita as outras 9 por conflito de versão (`422`) e mantém a integridade geométrica do estoque.
---

## 📈 Testes de Estresse e Concorrência (Autocannon)

Para simular 100 conexões simultâneas enviando vendas concorrentes por 30 segundos, utilize o script de benchmark configurado:

```bash
# Com o servidor rodando em uma janela do terminal, execute em outra:
node tests/benchmark.js <UUID_DO_PRODUTO>

```
*(O UUID do produto de teste é impresso na tela ao finalizar o comando `node tests/setup-db.js` no passo 1).*
