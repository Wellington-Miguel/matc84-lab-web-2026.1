"""
shared/retry.py
Exponential Backoff com Full Jitter — evita Thundering Herd.

Uso:
    from shared.retry import with_retry, RetryConfig

    result = await with_retry(
        lambda: httpx_client.post("/inventory/reserve", json=payload),
        config=RetryConfig(max_attempts=4, base_delay=0.5)
    )
"""
import asyncio
import random
import logging
from dataclasses import dataclass
from typing import Callable, Awaitable, TypeVar, Set

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Códigos HTTP que justificam retry (falhas transitórias)
RETRYABLE_STATUS_CODES: Set[int] = {429, 500, 502, 503, 504}


@dataclass
class RetryConfig:
    max_attempts: int = 4        # máximo de tentativas (incluindo a primeira)
    base_delay: float = 0.5      # delay inicial em segundos
    max_delay: float = 8.0       # teto do backoff em segundos
    jitter: str = "full"         # "full" | "equal"


class RetryExhaustedError(Exception):
    """Todas as tentativas falharam."""
    def __init__(self, last_error: Exception, attempts: int):
        self.last_error = last_error
        self.attempts = attempts
        super().__init__(f"Falha após {attempts} tentativa(s): {last_error}")


def _compute_delay(attempt: int, config: RetryConfig) -> float:
    """
    Calcula o tempo de espera antes do próximo retry.

    Full Jitter:  sorteia entre 0 e cap  → máxima dispersão de carga
    Equal Jitter: cap/2 + random(cap/2)  → garante tempo mínimo de espera
    """
    cap = min(config.max_delay, config.base_delay * (2 ** attempt))

    if config.jitter == "full":
        return random.uniform(0, cap)
    elif config.jitter == "equal":
        half = cap / 2
        return half + random.uniform(0, half)
    else:
        return cap


async def with_retry(
    fn: Callable[[], Awaitable[T]],
    config: RetryConfig = RetryConfig(),
    retryable_exceptions: tuple = (Exception,),
) -> T:
    """
    Executa `fn` com retry automático em caso de falha transitória.

    Args:
        fn: coroutine a ser executada (sem argumentos)
        config: configurações de retry
        retryable_exceptions: tipos de exceção que disparam retry

    Returns:
        Resultado de `fn` em caso de sucesso.

    Raises:
        RetryExhaustedError: se todas as tentativas falharem.
    """
    last_error: Exception = None

    for attempt in range(config.max_attempts):
        try:
            return await fn()

        except retryable_exceptions as err:
            last_error = err
            remaining = config.max_attempts - attempt - 1

            if remaining == 0:
                break  # não há mais tentativas

            delay = _compute_delay(attempt, config)
            logger.warning(
                "retry.scheduled",
                extra={
                    "attempt": attempt + 1,
                    "max_attempts": config.max_attempts,
                    "delay_ms": round(delay * 1000),
                    "error": str(err),
                    "remaining": remaining,
                }
            )
            await asyncio.sleep(delay)

    raise RetryExhaustedError(last_error, config.max_attempts)
