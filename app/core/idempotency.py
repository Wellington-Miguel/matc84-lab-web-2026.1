"""Idempotency key handling for request deduplication"""

import json
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.idempotencia_log import IdempotenciaLog


def generate_idempotency_key(key: str) -> str:
    """
    Validate and normalize idempotency key.

    Args:
        key: The idempotency key from request header

    Returns:
        The normalized key

    Raises:
        ValueError: If key is invalid
    """
    if not key or not isinstance(key, str):
        raise ValueError("Idempotency-Key must be a non-empty string")

    if len(key) > 255:
        raise ValueError("Idempotency-Key must be less than 255 characters")

    return key.strip()


def get_cached_response(db: Session, idempotency_key: str) -> Optional[dict]:
    """
    Retrieve cached response for idempotency key if it exists.

    Args:
        db: Database session
        idempotency_key: The idempotency key to lookup

    Returns:
        The cached response as dict, or None if not found
    """
    log_entry = db.query(IdempotenciaLog).filter(
        IdempotenciaLog.idempotencia_key == idempotency_key
    ).first()

    if log_entry:
        try:
            return json.loads(log_entry.resultado)
        except json.JSONDecodeError:
            return None

    return None


def store_idempotency_result(
    db: Session,
    idempotency_key: str,
    result: dict,
) -> bool:
    """
    Store the result of an idempotent operation.

    Args:
        db: Database session
        idempotency_key: The idempotency key for this operation
        result: The result to cache (as dict)

    Returns:
        True if successfully stored, False if key already exists
    """
    try:
        log_entry = IdempotenciaLog(
            idempotencia_key=idempotency_key,
            resultado=json.dumps(result),
        )
        db.add(log_entry)
        db.commit()
        return True
    except IntegrityError:
        # Key already exists - this is expected for retries
        db.rollback()
        return False
