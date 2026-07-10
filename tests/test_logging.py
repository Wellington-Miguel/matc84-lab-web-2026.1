"""Unit tests for the structured JSON logging module."""

import json
import logging

import pytest

from app.core.logging import (
    JSONFormatter,
    RequestIdFilter,
    configurar_logging,
    definir_request_id,
    obter_request_id,
)


def make_record(**extra) -> logging.LogRecord:
    record = logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="mensagem de teste",
        args=(),
        exc_info=None,
    )
    for chave, valor in extra.items():
        setattr(record, chave, valor)
    return record


class TestRequestIdContext:
    def test_definir_e_obter_request_id(self):
        definir_request_id("req-abc")
        assert obter_request_id() == "req-abc"
        definir_request_id(None)

    def test_valor_padrao_e_none(self):
        definir_request_id(None)
        assert obter_request_id() is None


class TestRequestIdFilter:
    def test_injeta_request_id_no_record(self):
        definir_request_id("req-xyz")
        record = make_record()

        assert RequestIdFilter().filter(record) is True
        assert record.request_id == "req-xyz"

        definir_request_id(None)

    def test_injeta_none_quando_sem_contexto(self):
        definir_request_id(None)
        record = make_record()

        RequestIdFilter().filter(record)

        assert record.request_id is None


class TestJSONFormatter:
    def test_formata_como_json_valido(self):
        record = make_record(request_id="req-1")
        payload = json.loads(JSONFormatter().format(record))

        assert payload["level"] == "INFO"
        assert payload["logger"] == "app.test"
        assert payload["message"] == "mensagem de teste"
        assert payload["request_id"] == "req-1"
        assert "timestamp" in payload

    def test_inclui_campos_extras_do_caller(self):
        record = make_record(request_id=None, http_method="GET", status_code=200)
        payload = json.loads(JSONFormatter().format(record))

        assert payload["http_method"] == "GET"
        assert payload["status_code"] == 200

    def test_inclui_excecao_quando_presente(self):
        try:
            raise ValueError("boom")
        except ValueError:
            import sys

            record = make_record(exc_info=sys.exc_info())

        payload = json.loads(JSONFormatter().format(record))

        assert "exception" in payload
        assert "boom" in payload["exception"]

    def test_mensagem_com_argumentos_de_formatacao(self):
        record = logging.LogRecord(
            name="app.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="valor: %s",
            args=("42",),
            exc_info=None,
        )
        payload = json.loads(JSONFormatter().format(record))

        assert payload["message"] == "valor: 42"


class TestConfigurarLogging:
    def test_instala_handler_json_unico(self):
        root = logging.getLogger()
        handlers_antes = list(root.handlers)
        try:
            configurar_logging("DEBUG")

            assert len(root.handlers) == 1
            assert isinstance(root.handlers[0].formatter, JSONFormatter)
            assert root.level == logging.DEBUG
        finally:
            root.handlers = handlers_antes

    def test_normaliza_nivel_case_insensitive(self):
        root = logging.getLogger()
        handlers_antes = list(root.handlers)
        try:
            configurar_logging("warning")
            assert root.level == logging.WARNING
        finally:
            root.handlers = handlers_antes
