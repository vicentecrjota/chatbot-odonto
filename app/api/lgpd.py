"""Endpoints LGPD — acesso, exportação e exclusão de dados de pacientes."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import require_api_key
from app.database import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/lgpd", tags=["Admin — LGPD"])


def _buscar_paciente(sb, clinic_id: str, phone: str) -> dict[str, Any]:
    """Busca paciente pelo telefone; lança 404 se não encontrado."""
    resp = (
        sb.table("patients")
        .select("id, name, phone, consent_given, consent_at, metadata")
        .eq("clinic_id", clinic_id)
        .eq("phone", phone)
        .limit(1)
        .execute()
    )
    data = getattr(resp, "data", None)
    if not data:
        raise HTTPException(status_code=404, detail="Paciente não encontrado.")
    return data[0]


# ---------------------------------------------------------------------------
# Exportação de dados (Art. 18, II — LGPD)
# ---------------------------------------------------------------------------

@router.get("/{clinic_id}/patients/{phone}/export", dependencies=[Depends(require_api_key)])
def exportar_dados_paciente(clinic_id: str, phone: str) -> dict[str, Any]:
    """
    Retorna todos os dados armazenados de um paciente:
    registro pessoal, histórico de conversas e consultas agendadas.
    """
    sb = get_supabase_client()
    paciente = _buscar_paciente(sb, clinic_id, phone)
    patient_id = paciente["id"]

    # Conversas (array de mensagens incluído)
    conv_resp = (
        sb.table("conversations")
        .select("id, messages, status, created_at")
        .eq("clinic_id", clinic_id)
        .eq("patient_phone", phone)
        .execute()
    )
    conversas = getattr(conv_resp, "data", []) or []

    # Consultas agendadas
    appt_resp = (
        sb.table("appointments")
        .select("id, datetime, procedure, status, reminder_sent")
        .eq("clinic_id", clinic_id)
        .eq("patient_id", patient_id)
        .execute()
    )
    consultas = getattr(appt_resp, "data", []) or []

    return {
        "paciente": paciente,
        "conversas": conversas,
        "consultas": consultas,
    }


# ---------------------------------------------------------------------------
# Revogação de consentimento (Art. 8, §5 — LGPD)
# ---------------------------------------------------------------------------

@router.patch(
    "/{clinic_id}/patients/{phone}/revoke-consent",
    dependencies=[Depends(require_api_key)],
)
def revogar_consentimento(clinic_id: str, phone: str) -> dict[str, Any]:
    """
    Revoga o consentimento LGPD do paciente.
    O paciente deixa de ser atendido pelo bot até dar novo consentimento.
    """
    sb = get_supabase_client()
    paciente = _buscar_paciente(sb, clinic_id, phone)

    resp = (
        sb.table("patients")
        .update({"consent_given": False, "consent_at": None})
        .eq("id", paciente["id"])
        .execute()
    )
    data = getattr(resp, "data", None)
    if not data:
        raise HTTPException(status_code=500, detail="Erro ao revogar consentimento.")

    logger.info("Consentimento revogado: clinic_id=%s phone=%s", clinic_id, phone)
    return {"detail": "Consentimento revogado. O paciente será solicitado a consentir novamente na próxima interação."}


# ---------------------------------------------------------------------------
# Exclusão de dados (Art. 18, VI — direito ao esquecimento)
# ---------------------------------------------------------------------------

@router.delete(
    "/{clinic_id}/patients/{phone}",
    dependencies=[Depends(require_api_key)],
    status_code=200,
)
def deletar_dados_paciente(clinic_id: str, phone: str) -> dict[str, Any]:
    """
    Remove todos os dados do paciente:
    - Consultas (cascade via FK)
    - Conversas (deletadas explicitamente — sem FK para patients)
    - Registro do paciente

    Irreversível. Confirme antes de chamar.
    """
    sb = get_supabase_client()
    paciente = _buscar_paciente(sb, clinic_id, phone)
    patient_id = paciente["id"]

    # Conversas não têm FK para patients — deletar explicitamente
    sb.table("conversations").delete().eq("clinic_id", clinic_id).eq("patient_phone", phone).execute()

    # Paciente (appointments cascadeiam automaticamente via FK ON DELETE CASCADE)
    sb.table("patients").delete().eq("id", patient_id).eq("clinic_id", clinic_id).execute()

    logger.info("Dados excluídos (LGPD): clinic_id=%s phone=%s", clinic_id, phone)
    return {"detail": f"Todos os dados do paciente {phone} foram removidos permanentemente."}
