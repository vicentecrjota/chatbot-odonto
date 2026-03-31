"""Endpoint de simulação — permite testar o pipeline sem WhatsApp."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.auth import require_api_key
from app.services.message_pipeline import processar_mensagem

router = APIRouter(prefix="/admin/simulate", tags=["Admin — Simulate"])


class SimulateRequest(BaseModel):
    phone: str
    message: str
    clinic_id: str


class SimulateResetRequest(BaseModel):
    phone: str
    clinic_id: str


@router.post("", dependencies=[Depends(require_api_key)])
def simulate(payload: SimulateRequest) -> dict:
    """Simula uma mensagem de paciente e retorna a resposta do bot."""
    resposta = processar_mensagem(payload.phone, payload.message, payload.clinic_id)
    return {"response": resposta}


@router.post("/reset", dependencies=[Depends(require_api_key)])
def simulate_reset(payload: SimulateResetRequest) -> dict:
    """Remove conversa e paciente do banco — reinicia como novo paciente."""
    from app.database import get_supabase_client
    sb = get_supabase_client()
    sb.table("conversations").delete().eq("clinic_id", payload.clinic_id).eq("patient_phone", payload.phone).execute()
    sb.table("patients").delete().eq("clinic_id", payload.clinic_id).eq("phone", payload.phone).execute()
    return {"detail": "Conversa e paciente removidos. Próxima mensagem iniciará como novo paciente."}
