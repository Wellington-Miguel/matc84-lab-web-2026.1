"""
shared/idempotency.py
Protocolo Check-then-Act — evita cobranças duplicadas e pedidos em duplicidade.

Uso:
    from shared.idempotency import IdempotencyGuard
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
        operation: Callable[[asyncpg.Connection], Awaitable[Any]],
        ttl_hours: int = 24,
    ) -> Any:
        """
        Executa `operation` exatamente uma vez para a `key` dada.

        Se a chave já existir → retorna resultado anterior (sem re-executar).
        Se não existir → executa, persiste chave+resultado atomicamente.
        """
        key = self.validate_key(key)

        async with self._pool.acquire() as conn:
            async with conn.transaction():

                await conn.execute(
                    """
                    SELECT pg_advisory_xact_lock(hashtext($1));
                    """,
                    key,
                )

                row = await conn.fetchrow(
                    """
                    SELECT result
                    FROM idempotency_keys
                    WHERE key = $1
                      AND expires_at > NOW()
                    """,
                    key,
                )

                if row:
                    return json.loads(row["result"])
                
                await conn.execute(
                    """
                    DELETE FROM idempotency_keys
                    WHERE key = $1
                    AND expires_at <= NOW()
                    """,
                    key,
                )

                result = await operation(conn)

                expires_at = (
                    datetime.now(timezone.utc)
                    + timedelta(hours=ttl_hours)
                )

                await conn.execute(
                    """
                    INSERT INTO idempotency_keys
                        (key, result, expires_at)
                    VALUES
                        ($1, $2, $3)
                    """,
                    key,
                    json.dumps(result, default=str),
                    expires_at,
                )

                return result

    @staticmethod
    def validate_key(key: Optional[str]) -> str:

        if not key:
            return str(uuid.uuid4())

        if len(key) > 255:
            raise ValueError(
                "Idempotency-Key deve possuir no máximo 255 caracteres"
            )

        return key