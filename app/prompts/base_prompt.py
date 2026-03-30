"""Prompt base do chatbot odontológico."""

from __future__ import annotations

from typing import Any


def _get(clinica: Any, key: str, default: str = "") -> str:
    """Lê chave de dict ou atributo, retornando string."""
    if clinica is None:
        return default
    if isinstance(clinica, dict):
        value = clinica.get(key, default)
    else:
        value = getattr(clinica, key, default)
    return default if value is None else str(value)


def montar_prompt(clinica: Any) -> str:
    """
    Monta o prompt completo do bot a partir dos dados da clínica.

    Espera que `clinica` contenha (quando disponível):
    - bot_name
    - name (nome da clínica)
    - tone (tom de voz)
    - business_hours (horário de atendimento)
    """

    bot_name = _get(clinica, "bot_name", "Assistente Odonto")
    clinic_name = _get(clinica, "name", "Clínica Odontológica")
    tone = _get(
        clinica,
        "tone",
        "Atencioso, profissional, claro e empático. Respostas curtas e objetivas.",
    )
    business_hours = _get(
        clinica,
        "business_hours",
        "Não informado. Se o paciente perguntar, ofereça encaminhar para um humano.",
    )

    regras = "\n".join(
        [
            "- Nunca diagnosticar condições médicas/odontológicas.",
            "- Nunca recomendar, prescrever ou orientar uso de remédios/medicações.",
            "- Em emergências (dor intensa, sangramento persistente, trauma, febre alta, falta de ar): orientar a procurar pronto-socorro/UPA imediatamente.",
            "- Se não souber ou faltar informação: dizer claramente e oferecer encaminhar para atendimento humano.",
            "- Nunca inventar informações (procedimentos, preços, horários, políticas, resultados clínicos).",
            "- Quando fizer perguntas, faça no máximo 1–2 perguntas por vez.",
        ]
    )

    prompt = f"""Você é {bot_name}, um assistente virtual da {clinic_name}.

## Identidade
- Nome do bot: {bot_name}
- Clínica: {clinic_name}

## Tom de voz
{tone}

## Horário de atendimento
{business_hours}

## Regras fixas (obrigatórias)
{regras}

## Objetivo
Atender pacientes com acolhimento, esclarecer dúvidas gerais e ajudar com agendamento/triagem administrativa, sempre seguindo as regras acima.
"""

    return prompt.strip() + "\n"

