"""Testes unitários do serviço de lembretes."""

from app.services.reminder_service import _formatar_data


def test_formata_data_iso_com_timezone():
    result = _formatar_data("2026-04-15T14:00:00+00:00")
    assert "15/04/2026" in result
    assert "14:00" in result


def test_formata_data_iso_com_z():
    result = _formatar_data("2026-04-15T09:30:00Z")
    assert "15/04/2026" in result
    assert "09:30" in result


def test_formata_data_invalida_retorna_original():
    invalido = "não-é-uma-data"
    result = _formatar_data(invalido)
    assert result == invalido
