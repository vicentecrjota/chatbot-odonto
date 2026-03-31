"""Limpeza automática de conversas expiradas."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.database import get_supabase_client

logger = logging.getLogger(__name__)


def limpar_conversas_expiradas() -> None:
    """
    Remove conversas onde expires_at < agora e status != 'human_takeover'.
    Conversas em handoff são preservadas — encerramento é manual pela recepção.
    Projetado para rodar diariamente via APScheduler.
    """
    sb = get_supabase_client()
    agora = datetime.now(timezone.utc).isoformat()

    resp = (
        sb.table("conversations")
        .delete()
        .lt("expires_at", agora)
        .neq("status", "human_takeover")
        .execute()
    )
    removidas = len(getattr(resp, "data", []) or [])
    if removidas:
        logger.info("Cleanup: %d conversa(s) expirada(s) removida(s).", removidas)
    else:
        logger.debug("Cleanup: nenhuma conversa expirada.")
