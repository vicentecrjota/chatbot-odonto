"""Endpoints de webhook para WhatsApp e Instagram (Meta)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from app.core.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()


# --- WHATSAPP ---

@router.get("/webhook/whatsapp", response_class=PlainTextResponse)
async def verify_whatsapp_webhook(
    mode: str | None = Query(None, alias="hub.mode"),
    token: str | None = Query(None, alias="hub.verify_token"),
    challenge: str | None = Query(None, alias="hub.challenge"),
) -> PlainTextResponse:
    settings = get_settings()
    if mode == "subscribe" and token == settings.meta_verify_token and challenge:
        return PlainTextResponse(content=challenge)
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook/whatsapp")
async def receive_whatsapp_message(request: Request) -> dict:
    body = await request.json()
    logger.info("WhatsApp webhook received: %s", body)
    # TODO: Etapa 2 - processar mensagem com IA
    # TODO: Etapa 3 - validar assinatura X-Hub-Signature-256
    return {"status": "ok"}


# --- INSTAGRAM ---

@router.get("/webhook/instagram", response_class=PlainTextResponse)
async def verify_instagram_webhook(
    mode: str | None = Query(None, alias="hub.mode"),
    token: str | None = Query(None, alias="hub.verify_token"),
    challenge: str | None = Query(None, alias="hub.challenge"),
) -> PlainTextResponse:
    settings = get_settings()
    if mode == "subscribe" and token == settings.meta_verify_token and challenge:
        return PlainTextResponse(content=challenge)
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook/instagram")
async def receive_instagram_message(request: Request) -> dict:
    body = await request.json()
    logger.info("Instagram webhook received: %s", body)
    return {"status": "ok"}
