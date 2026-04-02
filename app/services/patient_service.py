"""Gerenciamento de contexto clínico do paciente."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.database import get_supabase_client
from app.services.llm_service import chamar_llm

logger = logging.getLogger(__name__)

AWAITING_PATIENT_NAME_METADATA_KEY = "awaiting_patient_name"
_MAX_DISPLAY_NAME_LEN = 200

_EXTRACTION_PROMPT = """Analise a conversa abaixo e extraia APENAS informações clínicas relevantes sobre o paciente.
Retorne SOMENTE um objeto JSON válido, sem explicações, sem markdown.
Use null para campos não mencionados. Não invente, não infira — apenas o que foi explicitamente dito.

{
  "procedure_interest": "procedimento de interesse (ex: clareamento, implante, ortodontia) ou null",
  "symptoms": "sintomas relatados (ex: dor ao mastigar, sensibilidade) ou null",
  "urgency": "alta | media | baixa ou null",
  "notes": "outras observações clínicas relevantes (ex: bruxismo, alergia, gestante) ou null"
}

Conversa:
"""


def _extrair_contexto(user_message: str, bot_response: str) -> dict[str, Any] | None:
    """Chama o LLM para extrair contexto clínico estruturado da troca de mensagens."""
    conversa = f"Paciente: {user_message}\nBot: {bot_response}"
    try:
        raw = chamar_llm(_EXTRACTION_PROMPT, [{"role": "user", "content": conversa}])
        raw = raw.strip()
        # Remove blocos de código markdown se presentes
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)
        # Filtra apenas os campos esperados e não-nulos
        campos = ("procedure_interest", "symptoms", "urgency", "notes")
        return {k: v for k, v in data.items() if k in campos and v is not None}
    except Exception:
        logger.warning("Falha ao extrair contexto clínico; seguindo sem atualização.")
        return None


def _metadata_as_dict(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    return {}


def marcar_aguardando_nome_apos_lgpd(patient_id: str) -> None:
    """Após aceite do consentimento, marca que o próximo passo é coletar o nome."""
    sb = get_supabase_client()
    resp = (
        sb.table("patients")
        .select("metadata")
        .eq("id", patient_id)
        .limit(1)
        .execute()
    )
    data = getattr(resp, "data", None)
    meta: dict[str, Any] = {}
    if data and isinstance(data, list) and data[0]:
        meta = _metadata_as_dict(data[0].get("metadata"))
    meta[AWAITING_PATIENT_NAME_METADATA_KEY] = True
    sb.table("patients").update({"metadata": meta}).eq("id", patient_id).execute()


def salvar_nome_apos_consentimento_lgpd(patient_id: str, nome: str) -> None:
    """
    Persiste o nome informado pelo paciente após o consentimento LGPD
    e remove a flag de coleta pendente em metadata.
    """
    nome_limpo = nome.strip()[:_MAX_DISPLAY_NAME_LEN]
    if not nome_limpo:
        return

    sb = get_supabase_client()
    resp = (
        sb.table("patients")
        .select("metadata")
        .eq("id", patient_id)
        .limit(1)
        .execute()
    )
    meta: dict[str, Any] = {}
    data = getattr(resp, "data", None)
    if data and isinstance(data, list) and data[0]:
        meta = _metadata_as_dict(data[0].get("metadata"))
    meta.pop(AWAITING_PATIENT_NAME_METADATA_KEY, None)
    sb.table("patients").update({"name": nome_limpo, "metadata": meta}).eq("id", patient_id).execute()
    logger.info("Nome do paciente salvo após LGPD: patient_id=%s", patient_id)


def _upsert_patient(phone: str, clinic_id: str) -> str | None:
    """Garante que o paciente existe e retorna o id."""
    sb = get_supabase_client()
    resp = (
        sb.table("patients")
        .select("id")
        .eq("clinic_id", clinic_id)
        .eq("phone", phone)
        .limit(1)
        .execute()
    )
    data = getattr(resp, "data", None)
    if data and isinstance(data, list) and data[0]:
        return data[0]["id"]

    # Cria registro mínimo
    insert_resp = (
        sb.table("patients")
        .insert({"clinic_id": clinic_id, "phone": phone, "name": phone})
        .execute()
    )
    insert_data = getattr(insert_resp, "data", None)
    if insert_data and isinstance(insert_data, list) and insert_data[0]:
        return insert_data[0]["id"]
    return None


def carregar_contexto_paciente(phone: str, clinic_id: str) -> dict[str, Any]:
    """Retorna o metadata clínico atual do paciente (ou {} se não existir)."""
    sb = get_supabase_client()
    resp = (
        sb.table("patients")
        .select("metadata")
        .eq("clinic_id", clinic_id)
        .eq("phone", phone)
        .limit(1)
        .execute()
    )
    data = getattr(resp, "data", None)
    if data and isinstance(data, list) and data[0]:
        return data[0].get("metadata") or {}
    return {}


def atualizar_contexto_paciente(
    phone: str,
    clinic_id: str,
    user_message: str,
    bot_response: str,
) -> None:
    """
    Extrai contexto clínico da troca e faz merge com o metadata existente.
    Opera em background — erros são logados sem propagar.
    """
    novo = _extrair_contexto(user_message, bot_response)
    if not novo:
        return

    try:
        patient_id = _upsert_patient(phone, clinic_id)
        if not patient_id:
            logger.warning("Paciente não encontrado/criado para phone=%s", phone)
            return

        sb = get_supabase_client()
        atual_resp = (
            sb.table("patients")
            .select("metadata")
            .eq("id", patient_id)
            .limit(1)
            .execute()
        )
        atual_data = getattr(atual_resp, "data", None)
        atual = {}
        if atual_data and isinstance(atual_data, list) and atual_data[0]:
            atual = atual_data[0].get("metadata") or {}

        merged = {**atual, **novo}
        sb.table("patients").update({"metadata": merged}).eq("id", patient_id).execute()
        logger.info("Contexto do paciente %s atualizado: %s", phone, novo)
    except Exception:
        logger.exception("Erro ao atualizar contexto do paciente phone=%s", phone)
