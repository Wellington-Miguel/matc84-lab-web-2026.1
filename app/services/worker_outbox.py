"""Background worker for processing transactional outbox events"""

import asyncio
import logging

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.outbox import OutboxEvent

logger = logging.getLogger(__name__)

MAX_TENTATIVAS = 3
TAMANHO_LOTE = 100


class OutboxWorkerError(Exception):
    """Raised when outbox worker encounters a processing error"""
    pass


def processar_evento(db: Session, evento: OutboxEvent) -> bool:
    """
    Process a single outbox event and persist its new state.

    Returns True if processing succeeded, False otherwise.
    """
    try:
        evento.marcar_como_processado()
        db.commit()
        return True
    except Exception as exc:
        mensagem = f"Failed to process event {evento.id}: {exc}"
        logger.error(mensagem, exc_info=True)
        evento.registrar_tentativa_falha(mensagem)
        db.commit()
        return False


def processar_eventos_pendentes(db: Session, max_tentativas: int = MAX_TENTATIVAS) -> int:
    """
    Process pending outbox events in FIFO order.

    Returns the number of events processed successfully.
    """
    eventos = (
        db.query(OutboxEvent)
        .filter(
            OutboxEvent.processado.is_(False),
            OutboxEvent.tentativas < max_tentativas,
        )
        .order_by(OutboxEvent.criado_em)
        .limit(TAMANHO_LOTE)
        .all()
    )

    return sum(1 for evento in eventos if processar_evento(db, evento))


async def executar_worker_outbox(intervalo: int) -> None:
    """Poll the outbox table every `intervalo` seconds and process events."""
    logger.info("Outbox worker started with %ss interval", intervalo)

    while True:
        try:
            db = SessionLocal()
            try:
                processados = processar_eventos_pendentes(db)
                if processados:
                    logger.debug("Processed %s outbox events", processados)
            finally:
                db.close()
        except Exception as exc:
            logger.error("Error in outbox worker: %s", exc, exc_info=True)

        await asyncio.sleep(intervalo)


def iniciar_worker_outbox(intervalo: int) -> asyncio.Task:
    """Start the outbox worker as an asyncio background task."""
    task = asyncio.create_task(executar_worker_outbox(intervalo))
    logger.info("Outbox worker task created")
    return task


async def parar_worker_outbox(task: asyncio.Task) -> None:
    """Cancel the outbox worker background task."""
    if task.done():
        return

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        logger.info("Outbox worker task cancelled")
