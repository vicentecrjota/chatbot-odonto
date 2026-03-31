"""Autenticação via API Key para endpoints administrativos."""

from __future__ import annotations

from fastapi import Header, HTTPException

from app.core.config import get_settings


async def require_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> None:
    """Dependência FastAPI — valida X-API-Key no header."""
    settings = get_settings()
    if not settings.api_key:
        raise HTTPException(status_code=503, detail="API_KEY não configurada no servidor.")
    if x_api_key != settings.api_key.get_secret_value():
        raise HTTPException(status_code=401, detail="API Key inválida.")
