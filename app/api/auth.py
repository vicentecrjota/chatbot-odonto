"""Endpoints de autenticação do dashboard — vínculo usuário ↔ clínica."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.core.config import get_settings
from app.database import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])


class ClinicUserCreate(BaseModel):
    user_id: str
    clinic_id: str
    role: str = "admin"


def _verify_supabase_token(authorization: str) -> dict:
    """Valida o JWT do Supabase e retorna o payload do usuário."""
    settings = get_settings()
    sb = get_supabase_client()
    try:
        token = authorization.removeprefix("Bearer ").strip()
        resp = sb.auth.get_user(token)
        if not resp or not resp.user:
            raise HTTPException(status_code=401, detail="Token inválido ou expirado.")
        return {"id": resp.user.id, "email": resp.user.email}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Falha na validação do token.")


@router.get("/me")
def me(authorization: str = Header(...)) -> dict:
    """
    Retorna o usuário autenticado e o clinic_id vinculado.
    Chamado pelo dashboard logo após o login.
    """
    user = _verify_supabase_token(authorization)
    sb = get_supabase_client()

    resp = (
        sb.table("clinic_users")
        .select("clinic_id, role")
        .eq("user_id", user["id"])
        .limit(1)
        .execute()
    )
    data = getattr(resp, "data", None)
    if not data:
        raise HTTPException(
            status_code=404,
            detail="Usuário não vinculado a nenhuma clínica. Contate o administrador.",
        )

    return {
        "user_id": user["id"],
        "email": user["email"],
        "clinic_id": data[0]["clinic_id"],
        "role": data[0]["role"],
    }


@router.post("/clinic-users", status_code=201)
def vincular_usuario(
    payload: ClinicUserCreate,
    x_api_key: str = Header(..., alias="X-API-Key"),
) -> dict:
    """
    Vincula um usuário Supabase Auth a uma clínica.
    Chamado pelo admin durante o onboarding de uma nova clínica.
    Protegido pela API_KEY do backend (não pelo JWT da clínica).
    """
    settings = get_settings()
    if not settings.api_key or x_api_key != settings.api_key.get_secret_value():
        raise HTTPException(status_code=401, detail="API Key inválida.")

    sb = get_supabase_client()
    resp = (
        sb.table("clinic_users")
        .insert({
            "user_id": payload.user_id,
            "clinic_id": payload.clinic_id,
            "role": payload.role,
        })
        .execute()
    )
    data = getattr(resp, "data", None)
    if not data:
        raise HTTPException(status_code=500, detail="Erro ao vincular usuário.")

    logger.info("Usuário %s vinculado à clínica %s", payload.user_id, payload.clinic_id)
    return data[0]
