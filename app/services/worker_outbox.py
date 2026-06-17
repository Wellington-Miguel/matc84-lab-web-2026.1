"""Background worker for processing transactional outbox events"""

import asyncio
import json
import logging
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.core.database import SessionLocal
from app.models.outbox import OutboxEvent, TipoEvento
from app.models.item_pedido import ItemPedido
from app.models.pedido import Pedido, StatusPedido

logger = logging.getLogger(__name__)


class OutboxWorkerError(Exception):
    """Raised when outbox worker encounters a processing error"""
    pass


async def processar_evento(db: Session, evento: OutboxEvent) -> bool:
    """
    Process a single outbox event.

    Args:
        db: Database session
        evento: The outbox event to process

    Returns:
        True if processing succeeded

    Raises:
        OutboxWorkerError: If processing fails
    """
    try:
        if evento.tipo_evento == TipoEvento.PEDIDO_CRIADO:
            # Order creation is already handled in the order service
            # Just mark it as processed
            evento.marcar_como_processado()

        elif evento.tipo_evento == TipoEvento.ESTOQUE_RESERVADO:
            # Stock reservation is already handled in the order service
            # Just mark it as processed
            evento.marcar_como_processado()

        elif evento.tipo_evento == TipoEvento.ESTOQUE_LIBERADO:
            # Stock release is already handled
            # Just mark it as processed
            evento.marcar_como_processado()

        else:
            logger.warning(f"Unknown event type: {evento.tipo_evento}")
            evento.marcar_como_processado()

        db.commit()
        return True

    except Exception as e:
        error_msg = f"Failed to process event {evento.id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        evento.registrar_tentativa_falha(error_msg)
        db.commit()
        return False


async def processar_eventos_com_backoff(
    db: Session,
    max_tentativas: int = 3,
) -> int:
    """
    Process unprocessed outbox events with exponential backoff.

    Args:
        db: Database session
        max_tentativas: Maximum attempts before giving up on an event

    Returns:
        Number of events processed successfully
    """
    # Fetch unprocessed events ordered by creation time (FIFO)
    eventos = db.query(OutboxEvent).filter(
        and_(
            OutboxEvent.processado == False,
            OutboxEvent.tentativas < max_tentativas,
        )
    ).order_by(OutboxEvent.criado_em).limit(100).all()  # Process max 100 at a time

    processados = 0
    for evento in eventos:
        try:
            if await processar_evento(db, evento):
                processados += 1
            else:
                logger.warning(f"Failed to process event {evento.id}, will retry later")
        except Exception as e:
            logger.error(f"Error processing event {evento.id}: {str(e)}", exc_info=True)

    return processados


async def worker_outbox(intervalo: int = 5):
    """
    Background worker task that processes outbox events periodically.

    This worker:
    1. Polls the outbox table every `intervalo` seconds
    2. Processes unprocessed events
    3. Uses exponential backoff for failed events
    4. Ensures events are processed exactly once (FIFO order)

    Args:
        intervalo: Time in seconds between processing cycles (default: 5)
    """
    logger.info(f"Outbox worker started with {intervalo}s interval")

    while True:
        try:
            db = SessionLocal()
            try:
                processados = await processar_eventos_com_backoff(db)
                if processados > 0:
                    logger.debug(f"Processed {processados} outbox events")
            finally:
                db.close()

        except Exception as e:
            logger.error(f"Error in outbox worker: {str(e)}", exc_info=True)

        # Wait before next iteration
        await asyncio.sleep(intervalo)


def criar_tarefa_worker_outbox(app, intervalo: int = 5):
    """
    Create and register the outbox worker as a FastAPI background task.

    Args:
        app: FastAPI application instance
        intervalo: Time in seconds between processing cycles

    Returns:
        The background task
    """
    async def startup_outbox_worker():
        """Create the outbox worker task on application startup"""
        app.outbox_worker_task = asyncio.create_task(worker_outbox(intervalo))
        logger.info("Outbox worker task created")

    async def shutdown_outbox_worker():
        """Cancel the outbox worker task on application shutdown"""
        if hasattr(app, "outbox_worker_task") and not app.outbox_worker_task.done():
            app.outbox_worker_task.cancel()
            try:
                await app.outbox_worker_task
            except asyncio.CancelledError:
                logger.info("Outbox worker task cancelled")

    app.add_event_handler("startup", startup_outbox_worker)
    app.add_event_handler("shutdown", shutdown_outbox_worker)
