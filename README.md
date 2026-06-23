# MATC84 - Laboratório de Programação Web

Bem-vindo ao repositório oficial da disciplina **MATC84 - Laboratório de Programação Web**. Este espaço foi criado para acompanhar o desenvolvimento dos projetos práticos da nossa turma ao longo do semestre.

---

## 🌿 Equipe 01 - Projeto Distribuidora de Bebidas

Esta branch (`equipe-01-statelessness-e-estado-distribuido`) abriga a implementação do backend da **Distribuidora de Bebidas**, focado no pilar de **Statelessness e Estado Distribuído**.

### 🏗️ Arquitetura do Projeto

O serviço é um backend de alta performance construído em **Node.js com TypeScript e Fastify** que processa vendas concorrentes com garantias rígidas de integridade e resiliência:

1. **Estado Distribuído (PostgreSQL & DynamoDB):** 
   - O **PostgreSQL** gerencia o estado relacional persistente (estoque e fila de outbox).
   - O **DynamoDB** atua como uma camada rápida de cache distribuído de idempotência (fast-path).
2. **Garantia de Idempotência (Outbox Pattern):**
   - Cada requisição exige uma chave única no cabeçalho (`x-idempotency-key`).
   - Se a requisição cair no cache do DynamoDB, o processamento é evitado.
   - Em caso de falhas de rede com o DynamoDB, o [IdempotencyWorker.ts](distribuidora-bebidas/src/shared/services/IdempotencyWorker.ts) sincroniza o estado entre PostgreSQL e DynamoDB em background.
3. **Resolução de Concorrência (Optimistic Locking - OCC):**
   - Para manter o servidor totalmente *stateless*, as colisões de concorrência são resolvidas no banco através de uma coluna `version`. Cada transação valida se a versão recebida ainda é a mesma antes de decrementar o estoque, retornando `422` se houver colisão.
4. **Desligamento Gracioso (Graceful Shutdown):**
   - O servidor intercepta sinais de desligamento (`SIGINT`/`SIGTERM`) para parar os workers em background e liberar conexões pendentes de banco.

---

## 🛠️ Tecnologias Utilizadas
* **Backend:** Node.js (v22.17.0+) & Fastify (v5.x)
* **Linguagem:** TypeScript
* **Bancos de Dados:** PostgreSQL 16 & DynamoDB (SDK v3)
* **Testes:** Vitest (Suíte de Testes) & Autocannon (Benchmarking/Estresse)

---

## 🚀 Como Iniciar o Projeto Localmente

Navegue até a pasta do projeto de bebidas:
```bash
cd distribuidora-bebidas
```

### 1. Configurar o Banco de Dados
Certifique-se de que o PostgreSQL está rodando localmente (porta 5432).
Execute o script interativo de setup automatizado:
```bash
node tests/setup-db.js
```
O script solicitará suas credenciais do Postgres e irá:
* Criar o banco de dados `salesdb`.
* Rodar as migrações (criar tabelas `products` e `idempotency_outbox`).
* Inserir um produto de teste com estoque de `10000` unidades e versão `1`.
* Gerar um arquivo `.env` configurado automaticamente.

### 2. Rodar o Servidor
Execute o comando unificado de desenvolvimento que compila o TypeScript e inicializa o servidor automaticamente carregando as variáveis do `.env`:
```bash
npm run dev
```
*O servidor estará escutando em `http://localhost:3000`.*

---

## 🧪 Rodando Testes Automatizados
O projeto conta com testes unitários (para o fluxo de serviço) e de integração (validação de cabeçalhos, corpo e rotas HTTP em memória).
Para rodar a suíte inteira via Vitest:
```bash
npm test
```

---

## 📈 Testes de Estresse e Concorrência (Autocannon)
Para simular 100 conexões simultâneas enviando vendas concorrentes por 30 segundos, utilize o script de benchmark configurado:

```bash
# Com o servidor rodando em uma janela, execute em outra:
node tests/benchmark.js <UUID_DO_PRODUTO>
```
*(O UUID do produto de teste é impresso na tela ao finalizar o comando `node tests/setup-db.js` no passo 1).*
