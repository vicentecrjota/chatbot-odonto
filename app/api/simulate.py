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


@router.post("", dependencies=[Depends(require_api_key)])
def simulate(payload: SimulateRequest) -> dict:
    """Simula uma mensagem de paciente e retorna a resposta do bot."""
    resposta = processar_mensagem(payload.phone, payload.message, payload.clinic_id)
    return {"response": resposta}
