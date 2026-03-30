"""Endpoints de webhook para WhatsApp e Instagram (Meta)."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from app.core.config import get_settings
from app.database import get_supabase_client
from app.services.message_pipeline import processar_mensagem
from app.services.meta_service import send_instagram_message, send_whatsapp_message

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Signature validation
# ---------------------------------------------------------------------------

async def _verify_meta_signature(request: Request) -> None:
    """Valida X-Hub-Signature-256 usando META_APP_SECRET."""
    settings = get_settings()
    if not settings.meta_app_secret:
        # Se não configurado, ignora validação (útil em desenvolvimento)
        logger.warning("META_APP_SECRET não configurado; assinatura não validada.")
        return

    signature = request.headers.get("X-Hub-Signature-256", "")
    if not signature.startswith("sha256="):
        raise HTTPException(status_code=403, detail="Assinatura ausente ou inválida")

    body = await request.body()
    secret = settings.meta_app_secret.get_secret_value().encode()
    expected = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=403, detail="Assinatura inválida")


async def _parse_verified_json(request: Request) -> dict[str, Any]:
    """Valida assinatura e retorna o body como dict."""
    await _verify_meta_signature(request)
    body_bytes = await request.body()
    return json.loads(body_bytes)


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
    body = await _parse_verified_json(request)
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
            await asyncio.get_event_loop().run_in_executor(
                None, send_whatsapp_message, phone_number_id, phone, resposta
            )
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
    body = await _parse_verified_json(request)
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
            await asyncio.get_event_loop().run_in_executor(
                None, send_instagram_message, sender_id, resposta
            )
        except Exception:
            logger.exception("Erro ao processar mensagem de %s", sender_id)

    return {"status": "ok"}
