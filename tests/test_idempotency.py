"""Unit tests for app.core.idempotency, isolated from the order service."""

import pytest
from sqlalchemy.orm import Session

from app.core.idempotency import (
    normalize_idempotency_key,
    get_cached_response,
    store_idempotency_result,
)
from app.models.idempotencia_log import IdempotenciaLog


class TestNormalizeIdempotencyKey:
    def test_normaliza_chave_valida(self):
        assert normalize_idempotency_key("abc-123") == "abc-123"

    def test_remove_espacos_nas_bordas(self):
        assert normalize_idempotency_key("  abc-123  ") == "abc-123"

    def test_rejeita_chave_vazia(self):
        with pytest.raises(ValueError):
            normalize_idempotency_key("")

    def test_rejeita_none(self):
        with pytest.raises(ValueError):
            normalize_idempotency_key(None)

    def test_rejeita_chave_muito_longa(self):
        with pytest.raises(ValueError):
            normalize_idempotency_key("a" * 256)

    def test_aceita_chave_no_limite(self):
        chave = "a" * 255
        assert normalize_idempotency_key(chave) == chave


class TestGetCachedResponse:
    def test_retorna_none_quando_chave_nao_existe(self, db_session: Session):
        assert get_cached_response(db_session, "inexistente") is None

    def test_retorna_resultado_armazenado(self, db_session: Session):
        store_idempotency_result(db_session, "chave-1", {"id": 42, "total": 10.5})

        resultado = get_cached_response(db_session, "chave-1")

        assert resultado == {"id": 42, "total": 10.5}

    def test_retorna_none_para_json_corrompido(self, db_session: Session):
        log_entry = IdempotenciaLog(idempotencia_key="chave-corrompida", resultado="{invalido")
        db_session.add(log_entry)
        db_session.commit()

        assert get_cached_response(db_session, "chave-corrompida") is None


class TestStoreIdempotencyResult:
    def test_armazena_com_sucesso(self, db_session: Session):
        ok = store_idempotency_result(db_session, "chave-nova", {"id": 1})

        assert ok is True
        assert db_session.query(IdempotenciaLog).count() == 1

    def test_retorna_false_para_chave_duplicada(self, db_session: Session):
        store_idempotency_result(db_session, "chave-dup", {"id": 1})

        ok = store_idempotency_result(db_session, "chave-dup", {"id": 2})

        assert ok is False
        # Original result is preserved, not overwritten.
        assert get_cached_response(db_session, "chave-dup") == {"id": 1}

    def test_sessao_permanece_utilizavel_apos_conflito(self, db_session: Session):
        """A duplicate key rolls back internally, so the session must still
        accept further queries/writes afterwards."""
        store_idempotency_result(db_session, "chave-dup-2", {"id": 1})
        store_idempotency_result(db_session, "chave-dup-2", {"id": 2})

        ok = store_idempotency_result(db_session, "chave-outra", {"id": 3})

        assert ok is True
