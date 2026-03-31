"""Testes unitários do serviço de handoff (funções puras)."""

import pytest

from app.services.handoff_service import (
    checar_cenario_complexo,
    checar_loop,
    checar_pedido_explicito,
    extrair_tag_transferir,
)


# ---------------------------------------------------------------------------
# checar_pedido_explicito
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("msg", [
    "quero falar com atendente",
    "Falar com humano",
    "QUERO HUMANO",
    "me passa para atendente",
    "falar com a recepção",
    "não quero falar com bot",
])
def test_pedido_explicito_detectado(msg):
    assert checar_pedido_explicito(msg) is True


@pytest.mark.parametrize("msg", [
    "quero agendar uma consulta",
    "qual o horário de atendimento?",
    "dor de dente",
])
def test_pedido_explicito_nao_detectado(msg):
    assert checar_pedido_explicito(msg) is False


# ---------------------------------------------------------------------------
# checar_cenario_complexo
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("msg", [
    "tenho um plano odontológico",
    "quero reembolso",
    "vou acionar o PROCON",
    "erro médico no procedimento",
    "cobrou errado no meu cartão",
])
def test_cenario_complexo_detectado(msg):
    assert checar_cenario_complexo(msg) is True


@pytest.mark.parametrize("msg", [
    "quero fazer uma limpeza",
    "tenho dor de dente",
    "qual o preço do clareamento?",
])
def test_cenario_complexo_nao_detectado(msg):
    assert checar_cenario_complexo(msg) is False


# ---------------------------------------------------------------------------
# checar_loop
# ---------------------------------------------------------------------------

def _historico(n_user: int) -> list[dict]:
    msgs = []
    for i in range(n_user):
        msgs.append({"role": "user", "content": f"msg {i}"})
        msgs.append({"role": "assistant", "content": f"resp {i}"})
    return msgs


def test_loop_nao_detectado_abaixo_do_limite():
    assert checar_loop(_historico(7)) is False


def test_loop_detectado_no_limite():
    assert checar_loop(_historico(8)) is True


def test_loop_detectado_acima_do_limite():
    assert checar_loop(_historico(15)) is True


def test_loop_historico_vazio():
    assert checar_loop([]) is False


# ---------------------------------------------------------------------------
# extrair_tag_transferir
# ---------------------------------------------------------------------------

def test_extrai_tag_transferir():
    resposta = "Vou te encaminhar para um atendente. [TRANSFERIR:dor intensa]"
    transferir, motivo, limpa = extrair_tag_transferir(resposta)
    assert transferir is True
    assert motivo == "dor intensa"
    assert "[TRANSFERIR:" not in limpa


def test_extrai_tag_transferir_case_insensitive():
    resposta = "Aguarde. [transferir:convênio]"
    transferir, motivo, _ = extrair_tag_transferir(resposta)
    assert transferir is True
    assert motivo == "convênio"


def test_sem_tag_transferir():
    resposta = "Claro! Vou verificar o horário disponível para você."
    transferir, motivo, limpa = extrair_tag_transferir(resposta)
    assert transferir is False
    assert motivo == ""
    assert limpa == resposta
