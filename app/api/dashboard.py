"""Endpoints de dashboard — conversas, analytics e fila de handoff."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth import require_api_key
from app.database import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/dashboard", tags=["Admin — Dashboard"])


# ---------------------------------------------------------------------------
# Conversas
# ---------------------------------------------------------------------------

@router.get("/{clinic_id}/conversations", dependencies=[Depends(require_api_key)])
def listar_conversas(
    clinic_id: str,
    status: str | None = Query(None, description="Filtro por status (ex: active, human_takeover)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """
    Lista conversas de uma clínica com paginação.
    Retorna mensagens excluídas do payload para reduzir tamanho — use o endpoint de detalhe para lê-las.
    """
    sb = get_supabase_client()

    query = (
        sb.table("conversations")
        .select("id, patient_phone, status, created_at, expires_at")
        .eq("clinic_id", clinic_id)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
    )
    if status:
        query = query.eq("status", status)

    resp = query.execute()
    data = getattr(resp, "data", []) or []

    # Total (sem paginação) para o dashboard saber quantas páginas exibir.
    total_resp = (
        sb.table("conversations")
        .select("id", count="exact")
        .eq("clinic_id", clinic_id)
    )
    if status:
        total_resp = total_resp.eq("status", status)
    total_resp = total_resp.execute()
    total = getattr(total_resp, "count", None) or len(data)

    return {"total": total, "offset": offset, "limit": limit, "data": data}


@router.get("/{clinic_id}/conversations/{conversation_id}", dependencies=[Depends(require_api_key)])
def detalhe_conversa(clinic_id: str, conversation_id: str) -> dict[str, Any]:
    """Retorna uma conversa completa, incluindo o array de mensagens."""
    sb = get_supabase_client()
    resp = (
        sb.table("conversations")
        .select("*")
        .eq("clinic_id", clinic_id)
        .eq("id", conversation_id)
        .limit(1)
        .execute()
    )
    data = getattr(resp, "data", None)
    if not data:
        raise HTTPException(status_code=404, detail="Conversa não encontrada.")
    return data[0]


@router.delete(
    "/{clinic_id}/conversations/{conversation_id}",
    dependencies=[Depends(require_api_key)],
    status_code=204,
)
def deletar_conversa(clinic_id: str, conversation_id: str) -> None:
    """Remove uma conversa (LGPD — direito ao esquecimento por conversa)."""
    sb = get_supabase_client()
    sb.table("conversations").delete().eq("clinic_id", clinic_id).eq("id", conversation_id).execute()


# ---------------------------------------------------------------------------
# Fila de handoff
# ---------------------------------------------------------------------------

@router.get("/{clinic_id}/handoff", dependencies=[Depends(require_api_key)])
def fila_handoff(clinic_id: str) -> list[dict[str, Any]]:
    """
    Retorna conversas em status human_takeover, ordenadas da mais antiga para a mais nova
    (quem esperou mais aparece primeiro).
    """
    sb = get_supabase_client()
    resp = (
        sb.table("conversations")
        .select("id, patient_phone, status, created_at")
        .eq("clinic_id", clinic_id)
        .eq("status", "human_takeover")
        .order("created_at", desc=False)
        .execute()
    )
    return getattr(resp, "data", []) or []


@router.patch(
    "/{clinic_id}/handoff/{conversation_id}/resolve",
    dependencies=[Depends(require_api_key)],
)
def resolver_handoff(clinic_id: str, conversation_id: str) -> dict[str, Any]:
    """
    Marca uma conversa de handoff como resolvida (status → 'active'),
    devolvendo o controle ao bot.
    """
    sb = get_supabase_client()
    resp = (
        sb.table("conversations")
        .update({"status": "active"})
        .eq("clinic_id", clinic_id)
        .eq("id", conversation_id)
        .execute()
    )
    data = getattr(resp, "data", None)
    if not data:
        raise HTTPException(status_code=404, detail="Conversa não encontrada.")
    return data[0]


@router.patch(
    "/{clinic_id}/handoff/{conversation_id}/close",
    dependencies=[Depends(require_api_key)],
)
def fechar_conversa(clinic_id: str, conversation_id: str) -> dict[str, Any]:
    """Fecha uma conversa manualmente (status → 'closed')."""
    sb = get_supabase_client()
    resp = (
        sb.table("conversations")
        .update({"status": "closed"})
        .eq("clinic_id", clinic_id)
        .eq("id", conversation_id)
        .execute()
    )
    data = getattr(resp, "data", None)
    if not data:
        raise HTTPException(status_code=404, detail="Conversa não encontrada.")
    return data[0]


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

@router.get("/{clinic_id}/analytics", dependencies=[Depends(require_api_key)])
def analytics(clinic_id: str) -> dict[str, Any]:
    """
    Métricas consolidadas da clínica:
    - Total de conversas por status
    - Total de pacientes
    - Total de consultas agendadas (por status)
    - Lembretes enviados
    """
    sb = get_supabase_client()

    # Conversas por status
    conv_resp = (
        sb.table("conversations")
        .select("status")
        .eq("clinic_id", clinic_id)
        .execute()
    )
    conversas = getattr(conv_resp, "data", []) or []
    conv_por_status: dict[str, int] = {}
    for c in conversas:
        s = c.get("status", "unknown")
        conv_por_status[s] = conv_por_status.get(s, 0) + 1

    # Total de pacientes
    pac_resp = (
        sb.table("patients")
        .select("id", count="exact")
        .eq("clinic_id", clinic_id)
        .execute()
    )
    total_pacientes = getattr(pac_resp, "count", None) or 0

    # Pacientes com consentimento
    consent_resp = (
        sb.table("patients")
        .select("id", count="exact")
        .eq("clinic_id", clinic_id)
        .eq("consent_given", True)
        .execute()
    )
    total_com_consentimento = getattr(consent_resp, "count", None) or 0

    # Consultas por status
    appt_resp = (
        sb.table("appointments")
        .select("status, reminder_sent")
        .eq("clinic_id", clinic_id)
        .execute()
    )
    appointments = getattr(appt_resp, "data", []) or []
    appt_por_status: dict[str, int] = {}
    lembretes_enviados = 0
    for a in appointments:
        s = a.get("status", "unknown")
        appt_por_status[s] = appt_por_status.get(s, 0) + 1
        if a.get("reminder_sent"):
            lembretes_enviados += 1

    return {
        "conversas": {
            "total": len(conversas),
            "por_status": conv_por_status,
        },
        "pacientes": {
            "total": total_pacientes,
            "com_consentimento": total_com_consentimento,
        },
        "consultas": {
            "total": len(appointments),
            "por_status": appt_por_status,
            "lembretes_enviados": lembretes_enviados,
        },
    }
