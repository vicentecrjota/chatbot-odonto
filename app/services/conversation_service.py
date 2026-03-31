"""Persistência e carregamento do histórico de conversas."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.database import get_supabase_client

logger = logging.getLogger(__name__)

_HISTORY_LIMIT = 10  # últimas N mensagens (5 trocas)
_TTL_DAYS = 30       # TTL rolling: cada mensagem renova por 30 dias


def _expires_at() -> str:
    return (datetime.now(timezone.utc) + timedelta(days=_TTL_DAYS)).isoformat()


def carregar_historico(phone: str, clinic_id: str) -> list[dict[str, str]]:
    """
    Retorna as últimas _HISTORY_LIMIT mensagens da conversa
    no formato [{"role": "user"|"assistant", "content": "..."}].
    """
    sb = get_supabase_client()
    resp = (
        sb.table("conversations")
        .select("messages")
        .eq("clinic_id", clinic_id)
        .eq("patient_phone", phone)
        .limit(1)
        .execute()
    )
    data = getattr(resp, "data", None)
    if not data or not isinstance(data, list) or not data[0]:
        return []

    messages = data[0].get("messages", [])
    if not isinstance(messages, list):
        return []

    return messages[-_HISTORY_LIMIT:]


def salvar_mensagens(
    phone: str,
    clinic_id: str,
    user_message: str,
    bot_response: str,
) -> None:
    """
    Append da mensagem do usuário e da resposta do bot no histórico.
    Cria a conversa se ainda não existir.
    """
    sb = get_supabase_client()

    resp = (
        sb.table("conversations")
        .select("id, messages")
        .eq("clinic_id", clinic_id)
        .eq("patient_phone", phone)
        .limit(1)
        .execute()
    )
    data = getattr(resp, "data", None)
    existing = data[0] if data and isinstance(data, list) and data[0] else None

    new_entries: list[dict[str, Any]] = [
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": bot_response},
    ]

    try:
        if existing:
            current: list = existing.get("messages", []) or []
            updated = current + new_entries
            sb.table("conversations").update({
                "messages": updated,
                "expires_at": _expires_at(),
            }).eq("id", existing["id"]).execute()
        else:
            sb.table("conversations").insert(
                {
                    "clinic_id": clinic_id,
                    "patient_phone": phone,
                    "messages": new_entries,
                    "status": "active",
                    "expires_at": _expires_at(),
                }
            ).execute()
    except Exception:
        logger.exception(
            "Erro ao salvar histórico para phone=%s clinic_id=%s", phone, clinic_id
        )
