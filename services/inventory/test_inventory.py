"""
services/inventory/test_inventory.py
Testes e exemplos de uso do Inventory Service
"""

# ────── EXEMPLOS DE REQUISIÇÕES HTTP ──────────────────────────────────────────

# 1. OBTER ESTOQUE ATUAL
# GET http://localhost:8001/inventory/SKU-001
# Response (200):
# {
#   "sku_id": "SKU-001",
#   "quantity": 100,
#   "version": 1,
#   "updated_at": "2026-07-01T14:00:00+00:00"
# }


# 2. DEDUZIR ESTOQUE (Com OCC - Optimistic Concurrency Control)
# POST http://localhost:8001/inventory/SKU-001/deduct
# Body:
# {
#   "quantity": 10
# }
# Response (200):
# {
#   "sku_id": "SKU-001",
#   "deducted": 10,
#   "remaining": 90,
#   "version": 2
# }

# Erro: Estoque insuficiente (409 CONFLICT)
# POST http://localhost:8001/inventory/SKU-001/deduct
# Body: { "quantity": 200 }
# Response:
# {
#   "detail": "Estoque insuficiente. Disponível: 100"
# }

# Erro: SKU não encontrado (404)
# POST http://localhost:8001/inventory/SKU-INVALID/deduct
# Response:
# {
#   "detail": "SKU SKU-INVALID não encontrado"
# }


# 3. REPOR ESTOQUE
# POST http://localhost:8001/inventory/SKU-001/replenish
# Body:
# {
#   "quantity": 50
# }
# Response (200):
# {
#   "sku_id": "SKU-001",
#   "added": 50,
#   "total": 150
# }


# 4. HEALTH CHECK
# GET http://localhost:8001/health
# Response (200):
# {
#   "status": "healthy",
#   "checks": {
#     "db": "ok",
#     "redis": "ok"
#   }
# }


# 5. MÉTRICAS PROMETHEUS
# GET http://localhost:8001/metrics
# (Scrape para Prometheus)


# ────── EXEMPLO DE CENÁRIO CONCORRENTE (OCC) ──────────────────────────────────

# Situação: Duas requisições simultâneas tentam deduzir do mesmo SKU
#
# Request A (Thread 1):
#   1. Lê: quantity=100, version=1 (do Redis ou DB)
#   2. Calcula: 100 - 5 = 95
#   3. Tenta UPDATE com WHERE version=1
#   ✓ Sucesso: Atualiza para quantity=95, version=2
#   4. Invalida cache Redis
#
# Request B (Thread 2):
#   1. Lê: quantity=100, version=1 (do Redis antes da invalidação)
#   2. Calcula: 100 - 3 = 97
#   3. Tenta UPDATE com WHERE version=1
#   ✗ FALHA: Version não é 1 mais (é 2)
#   4. Incrementa métrica OCC_CONFLICT
#   5. Invalida cache e RETRY
#   6. Lê novamente: quantity=95, version=2
#   7. Calcula: 95 - 3 = 92
#   8. Tenta UPDATE com WHERE version=2
#   ✓ Sucesso: Atualiza para quantity=92, version=3
#
# Resultado final: quantity=92 (correto!)


# ────── INTEGRAÇÃO COM ORDER SERVICE ───────────────────────────────────────────

# Order Service já valida estoque chamando Inventory:
#
# async def _check_stock(sku_id: str, quantity: int) -> bool:
#     raw = await redis_client.get(f"stock:{sku_id}")
#     if raw is None:
#         # Consulta Inventory Service (ou diretamente o DB local)
#         row = await db_pool.fetchrow(
#             "SELECT quantity FROM inventory WHERE sku_id = $1",
#             sku_id
#         )
#
# Para integração via HTTP (recomendado em produção):
#
# async def _check_stock_via_inventory_service(sku_id: str, quantity: int) -> bool:
#     async with httpx.AsyncClient() as client:
#         response = await client.get(
#             f"http://inventory-service:8001/inventory/{sku_id}",
#             timeout=5.0
#         )
#         if response.status_code == 404:
#             return False
#         data = response.json()
#         return data["quantity"] >= quantity
