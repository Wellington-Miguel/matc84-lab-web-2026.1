"""
services/inventory/test_inventory.py
Testes e exemplos de uso do Inventory Service
"""

# Exemplo de cenário concorrente (OCC)
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
