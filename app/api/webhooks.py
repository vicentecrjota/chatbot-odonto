"""Endpoints de webhook para WhatsApp e Instagram (Meta)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from app.core.config import get_settings
from app.database import get_supabase_client
from app.services.message_pipeline import processar_mensagem

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clinic_id_by_whatsapp(phone_number_id: str) -> str | None:
    sb = get_supabase_client()
    resp = (
        sb.table("clinics")
        .select("id")
        .eq("whatsapp_phone_number_id", phone_number_id)
        .limit(1)
        .execute()
    )
    data = getattr(resp, "data", None)
    if data and isinstance(data, list) and data[0]:
        return data[0]["id"]
    return None


def _clinic_id_by_instagram(page_id: str) -> str | None:
    sb = get_supabase_client()
    resp = (
        sb.table("clinics")
        .select("id")
        .eq("instagram_page_id", page_id)
        .limit(1)
        .execute()
    )
    data = getattr(resp, "data", None)
    if data and isinstance(data, list) and data[0]:
        return data[0]["id"]
    return None


def _extract_whatsapp(body: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Extrai lista de (phone, message_text, phone_number_id) do payload Meta."""
    results = []
    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            phone_number_id = value.get("metadata", {}).get("phone_number_id", "")
            for msg in value.get("messages", []):
                if msg.get("type") != "text":
                    continue
                phone = msg.get("from", "")
                text = msg.get("text", {}).get("body", "")
                if phone and text and phone_number_id:
                    results.append((phone, text, phone_number_id))
    return results


def _extract_instagram(body: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Extrai lista de (sender_id, message_text, page_id) do payload Meta."""
    results = []
    for entry in body.get("entry", []):
        page_id = entry.get("id", "")
        for messaging in entry.get("messaging", []):
            sender_id = messaging.get("sender", {}).get("id", "")
            text = messaging.get("message", {}).get("text", "")
            if sender_id and text and page_id:
                results.append((sender_id, text, page_id))
    return results


# ---------------------------------------------------------------------------
# WHATSAPP
# ---------------------------------------------------------------------------

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

    mensagens = _extract_whatsapp(body)
    if not mensagens:
        return {"status": "ok"}

    for phone, text, phone_number_id in mensagens:
        clinic_id = await asyncio.get_event_loop().run_in_executor(
            None, _clinic_id_by_whatsapp, phone_number_id
        )
        if not clinic_id:
            logger.warning("Clínica não encontrada para phone_number_id=%s", phone_number_id)
            continue

        try:
            resposta = await asyncio.get_event_loop().run_in_executor(
                None, processar_mensagem, phone, text, clinic_id
            )
            logger.info("Resposta gerada para %s: %s", phone, resposta)
            # TODO: Etapa 3 — enviar resposta via Meta API (send_whatsapp_message)
        except Exception:
            logger.exception("Erro ao processar mensagem de %s", phone)

    return {"status": "ok"}


# ---------------------------------------------------------------------------
# INSTAGRAM
# ---------------------------------------------------------------------------

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

    mensagens = _extract_instagram(body)
    if not mensagens:
        return {"status": "ok"}

    for sender_id, text, page_id in mensagens:
        clinic_id = await asyncio.get_event_loop().run_in_executor(
            None, _clinic_id_by_instagram, page_id
        )
        if not clinic_id:
            logger.warning("Clínica não encontrada para instagram_page_id=%s", page_id)
            continue

        try:
            resposta = await asyncio.get_event_loop().run_in_executor(
                None, processar_mensagem, sender_id, text, clinic_id
            )
            logger.info("Resposta gerada para %s: %s", sender_id, resposta)
            # TODO: Etapa 3 — enviar resposta via Meta API (send_instagram_message)
        except Exception:
            logger.exception("Erro ao processar mensagem de %s", sender_id)

    return {"status": "ok"}
