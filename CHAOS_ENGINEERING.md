# Guia de Uso — Chaos Engineering (Middleware do Caos)

Este documento explica como utilizar o módulo de Chaos Engineering implementado na aplicação, quais comandos executar e o que esperar de cada um.

---

## O que foi implementado?

Foram adicionados três mecanismos de injeção de falhas:

1. **ChaosMiddleware** (`app/core/chaos.py`) — injeta latência aleatória e erros 500 em requisições normais.
2. **Flag de queda de banco** (`app/api/v1/rotas_saude.py`) — simula perda de conexão com o banco de dados no endpoint `/ready`.
3. **Rota de controle** (`POST /chaos/toggle-db`) — ativa ou desativa a queda simulada do banco via API.

---

## Pré-requisitos

- Ambiente virtual Python ativado
- Uvicorn rodando (com `--reload` para reiniciar automaticamente ao salvar os arquivos)
- `curl` disponível no terminal

---

## Passo a passo para testar

### 1. Subir a aplicação com o caos habilitado

O Chaos Engineering vem **desabilitado por padrão** — nenhuma falha é injetada a menos que você o ligue explicitamente. Para os experimentos abaixo, suba o servidor com `CHAOS_ENABLED=true`:

```bash
# Linux/macOS
CHAOS_ENABLED=true uvicorn app.main:app --reload

# Windows (PowerShell)
$env:CHAOS_ENABLED="true"; uvicorn app.main:app --reload
```

O Uvicorn reinicia automaticamente sempre que você salvar alterações nos arquivos.

> Sem `CHAOS_ENABLED=true`, o `ChaosMiddleware` deixa todas as requisições passarem intactas — é o comportamento seguro para qualquer ambiente que não seja um experimento controlado.

---

### 2. Testar o ChaosMiddleware (latência + erro 500)

Execute o comando abaixo várias vezes seguidas:

```bash
curl -i http://localhost:8000/api/v1/produtos
```

**O que esperar:**
- Em ~30% das requisições, a resposta vai demorar entre 1 e 3 segundos (latência simulada).
- Em ~20% das requisições, você receberá uma resposta `HTTP 500` com a mensagem:
  ```
  💥 Chaos Engineering: Falha simulada pelo Middleware do Caos!
  ```
- As demais requisições serão respondidas normalmente.

> As rotas `/`, `/health`, `/ready`, `/docs` e `/openapi.json` são **ignoradas** pelo middleware e nunca sofrem esse caos.

---

### 3. Ativar a queda simulada do banco de dados

```bash
curl -X POST http://localhost:8000/chaos/toggle-db
```

**Resposta esperada:**
```json
{"message": "O ataque de caos ao banco de dados foi ATIVADO!"}
```

> Este endpoint é **recusado com HTTP 403** se `CHAOS_ENABLED` não estiver habilitado — a queda de banco só pode ser armada durante um experimento explicitamente ligado, nunca por acidente num ambiente real.

---

### 4. Verificar o impacto no health check de prontidão

Com a queda do banco ativada, chame o endpoint de readiness:

```bash
curl -i http://localhost:8000/ready
```

**Resposta esperada:**
```
HTTP/1.1 503 Service Unavailable

💥 Chaos Engineering: Conexão com o banco de dados perdida (Falha Simulada)!
```

---

### 5. Desativar o caos no banco de dados

Execute o mesmo comando de toggle novamente:

```bash
curl -X POST http://localhost:8000/chaos/toggle-db
```

**Resposta esperada:**
```json
{"message": "O ataque de caos ao banco de dados foi DESATIVADO!"}
```

---

### 6. Confirmar que o sistema voltou ao normal

```bash
curl -i http://localhost:8000/ready
```

**Resposta esperada:**
```json
{"status": "ready", "service": "beverage-distributor", "database": "connected"}
```

---

## Resumo dos comandos

| Ação | Comando |
|---|---|
| Testar latência e erro 500 | `curl -i http://localhost:8000/api/v1/produtos` |
| Ativar queda do banco | `curl -X POST http://localhost:8000/chaos/toggle-db` |
| Verificar readiness com caos | `curl -i http://localhost:8000/ready` |
| Desativar queda do banco | `curl -X POST http://localhost:8000/chaos/toggle-db` |
| Confirmar retorno ao normal | `curl -i http://localhost:8000/ready` |

---

## Configurações do Middleware (variáveis de ambiente)

Todas são lidas na inicialização (via `app/core/config.py`) e têm defaults seguros:

| Variável | Valor padrão | Descrição |
|---|---|---|
| `CHAOS_ENABLED` | `False` | Liga/desliga todo o middleware |
| `CHAOS_ERROR_RATE` | `0.2` | Probabilidade de erro 500 (20%) |
| `CHAOS_LATENCY_RATE` | `0.3` | Probabilidade de latência (30%) |
| `CHAOS_MIN_LATENCY` | `1.0` | Atraso mínimo em segundos |
| `CHAOS_MAX_LATENCY` | `3.0` | Atraso máximo em segundos |

## Observabilidade do caos

Toda falha injetada é contabilizada na métrica Prometheus **`chaos_faults_injected_total`**, rotulada por tipo, e exposta em `GET /metrics`:

| Rótulo `tipo` | Origem |
|---|---|
| `latency` | Atraso injetado pelo `ChaosMiddleware` |
| `error` | Erro 500 injetado pelo `ChaosMiddleware` |
| `db_outage` | Queda de banco simulada no `/ready` (`toggle-db`) |

Isso torna o raio de explosão de um experimento visível em tempo real e permite, na análise de error budget, **separar as falhas injetadas das falhas orgânicas** ao interpretar o SLI de disponibilidade.

Exemplo de consulta ao expor as métricas:
```bash
curl -s http://localhost:8000/metrics | grep chaos_faults_injected_total
# chaos_faults_injected_total{tipo="error"} 7.0
# chaos_faults_injected_total{tipo="latency"} 11.0
```