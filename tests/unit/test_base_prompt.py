"""Testes unitários da montagem do prompt base."""

from app.prompts.base_prompt import montar_prompt


def test_prompt_com_clinica_completa():
    clinica = {
        "name": "Clínica Sorriso",
        "bot_name": "Sofia",
        "tone": "Amigável e profissional.",
        "business_hours": "Seg-Sex 8h-18h",
    }
    prompt = montar_prompt(clinica)
    assert "Sofia" in prompt
    assert "Clínica Sorriso" in prompt
    assert "Amigável e profissional." in prompt
    assert "Seg-Sex 8h-18h" in prompt


def test_prompt_sem_dados_usa_defaults():
    prompt = montar_prompt({})
    assert "Assistente Odonto" in prompt
    assert "Clínica Odontológica" in prompt


def test_prompt_com_none_usa_defaults():
    prompt = montar_prompt(None)
    assert "Assistente Odonto" in prompt


def test_prompt_contem_regras_obrigatorias():
    prompt = montar_prompt({})
    assert "Nunca diagnosticar" in prompt
    assert "emergências" in prompt.lower()
    assert "TRANSFERIR" in prompt


def test_prompt_contem_fluxo_agendamento():
    prompt = montar_prompt({})
    assert "AGENDAR" in prompt
    assert "start_iso" in prompt


def test_prompt_nao_termina_com_whitespace_excessivo():
    prompt = montar_prompt({})
    assert prompt == prompt.strip() + "\n"
