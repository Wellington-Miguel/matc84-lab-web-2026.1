"""Unit tests for the OutboxEvent model's state-transition helper methods."""

from app.models.outbox import OutboxEvent, TipoEvento


def make_event(**overrides) -> OutboxEvent:
    """Build an OutboxEvent as it looks once persisted: Column(default=...)
    values (processado, tentativas) are only materialized by SQLAlchemy on
    flush/load, so tests construct instances with those defaults explicit."""
    defaults = dict(
        tipo_evento=TipoEvento.PEDIDO_CRIADO,
        agregado_id=1,
        dados='{"pedido_id": 1}',
        processado=False,
        tentativas=0,
    )
    defaults.update(overrides)
    return OutboxEvent(**defaults)


class TestMarcarComoProcessado:
    def test_marca_processado_true(self):
        evento = make_event()
        evento.marcar_como_processado()
        assert evento.processado is True

    def test_zera_tentativas_e_erro(self):
        evento = make_event(tentativas=2, erro_mensagem="falha anterior")
        evento.marcar_como_processado()
        assert evento.tentativas == 0
        assert evento.erro_mensagem is None


class TestRegistrarTentativaFalha:
    def test_incrementa_tentativas(self):
        evento = make_event()
        evento.registrar_tentativa_falha("erro 1")
        evento.registrar_tentativa_falha("erro 2")
        assert evento.tentativas == 2

    def test_armazena_mensagem_de_erro(self):
        evento = make_event()
        evento.registrar_tentativa_falha("timeout de conexão")
        assert evento.erro_mensagem == "timeout de conexão"

    def test_atualiza_timestamp_da_ultima_tentativa(self):
        evento = make_event()
        assert evento.ultima_tentativa_em is None
        evento.registrar_tentativa_falha("erro")
        assert evento.ultima_tentativa_em is not None

    def test_nao_marca_como_processado(self):
        evento = make_event()
        evento.registrar_tentativa_falha("erro")
        assert evento.processado is False


class TestObterDados:
    def test_retorna_dict_parseado(self):
        evento = make_event(dados='{"pedido_id": 42, "total": 10.5}')
        assert evento.obter_dados() == {"pedido_id": 42, "total": 10.5}

    def test_retorna_dict_vazio_para_json_invalido(self):
        evento = make_event(dados="não é json")
        assert evento.obter_dados() == {}
