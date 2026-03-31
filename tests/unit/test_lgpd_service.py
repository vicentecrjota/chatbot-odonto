"""Testes unitários do serviço LGPD (funções puras de detecção de keywords)."""

import pytest

from app.services.lgpd_service import _e_nao, _e_sim


@pytest.mark.parametrize("msg", [
    "sim", "SIM", "S", "s", "aceito", "Aceito",
    "concordo", "ok", "OK", "yes", "pode", "claro", "tudo bem",
])
def test_e_sim(msg):
    assert _e_sim(msg) is True


@pytest.mark.parametrize("msg", [
    "não", "nao", "NAO", "NÃO", "n", "N",
    "recuso", "no", "NO", "nunca", "negativo",
])
def test_e_nao(msg):
    assert _e_nao(msg) is True


@pytest.mark.parametrize("msg", [
    "quero agendar",
    "oi tudo bem",
    "talvez",
    "",
])
def test_nem_sim_nem_nao(msg):
    assert _e_sim(msg) is False
    assert _e_nao(msg) is False


def test_sim_com_ponto_final():
    """Pontuação ao final não deve afetar o reconhecimento."""
    assert _e_sim("sim.") is True


def test_nao_com_ponto_final():
    assert _e_nao("não.") is True
