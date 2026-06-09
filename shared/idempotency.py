"""
shared/idempotency.py
Protocolo Check-then-Act — evita cobranças duplicadas e pedidos em duplicidade.

O servidor verifica a chave, executa a lógica e persiste chave+resultado
em uma única transação atômica.

Uso:
    from shared.idempotency import IdempotencyGuard

    guard = IdempotencyGuard(db_pool)

    result = await guard.execute(
        key=request.headers["idempotency-key"],
        operation=lambda: create_order_in_db(payload),
        ttl_hours=24,
    )
"""
import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Awaitable, Optional
import asyncpg


class DuplicateRequestError(Exception):
    """A requisição já foi processada — retorna resultado anterior."""
    def __init__(self, cached_result: Any):
        self.cached_result = cached_result
        super().__init__("Requisição já processada (idempotência)")


class IdempotencyGuard:
    """
    Implementa o fluxo Check-then-Act com atomicidade garantida.

    Todas as operações ocorrem dentro de uma única transação PostgreSQL,
    garantindo que a chave e o resultado sejam persistidos juntos.
    """

    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def execute(
        self,
        key: str,
        operation: Callable[[], Awaitable[Any]],
        ttl_hours: int = 24,
    ) -> Any:
        """
        Executa `operation` exatamente uma vez para a `key` dada.

        Se a chave já existir → retorna resultado anterior (sem re-executar).
        Se não existir → executa, persiste chave+resultado atomicamente.
        """
        if not key or len(key) > 255:
            raise ValueError("Idempotency-Key deve ter entre 1 e 255 caracteres")

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # 1. Verifica existência da chave (dentro da transação)
                row = await conn.fetchrow(
                    "SELECT result FROM idempotency_keys WHERE key = $1 AND expires_at > NOW()",
                    key,
                )

                if row:
                    # Short-circuit: retorna resultado da primeira execução
                    return json.loads(row["result"])

                # 2. Executa a lógica de negócio
                result = await operation()

                # 3. Persiste chave + resultado na MESMA transação
                expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
                await conn.execute(
                    """
                    INSERT INTO idempotency_keys (key, result, expires_at)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (key) DO NOTHING
                    """,
                    key,
                    json.dumps(result, default=str),
                    expires_at,
                )

                return result

    @staticmethod
    def validate_key(key: Optional[str]) -> str:
        """Valida e retorna a chave, gerando uma se não fornecida."""
        if not key:
            return str(uuid.uuid4())
        if len(key) > 255:
            raise ValueError("Idempotency-Key muito longa")
        return key
