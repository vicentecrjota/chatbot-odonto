"""Envio de mensagens via Meta Cloud API (WhatsApp e Instagram)."""

from __future__ import annotations

import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_META_GRAPH_BASE = "https://graph.facebook.com/v19.0"
_TIMEOUT = 15.0


def _access_token() -> str:
    settings = get_settings()
    if not settings.meta_access_token:
        raise RuntimeError("META_ACCESS_TOKEN não configurado.")
    return settings.meta_access_token.get_secret_value()


def send_whatsapp_message(phone_number_id: str, to: str, text: str) -> None:
    """Envia mensagem de texto via WhatsApp Cloud API."""
    url = f"{_META_GRAPH_BASE}/{phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }
    headers = {"Authorization": f"Bearer {_access_token()}"}

    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
        logger.info("WhatsApp message sent to %s", to)
    except httpx.HTTPStatusError as exc:
        logger.error(
            "Erro ao enviar WhatsApp para %s: %s %s",
            to,
            exc.response.status_code,
            exc.response.text,
        )
        raise
    except httpx.RequestError as exc:
        logger.error("Falha de conexão ao enviar WhatsApp para %s: %s", to, exc)
        raise


def send_instagram_message(recipient_id: str, text: str) -> None:
    """Envia mensagem de texto via Instagram Messaging API."""
    url = f"{_META_GRAPH_BASE}/me/messages"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text},
    }
    headers = {"Authorization": f"Bearer {_access_token()}"}

    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
        logger.info("Instagram message sent to %s", recipient_id)
    except httpx.HTTPStatusError as exc:
        logger.error(
            "Erro ao enviar Instagram para %s: %s %s",
            recipient_id,
            exc.response.status_code,
            exc.response.text,
        )
        raise
    except httpx.RequestError as exc:
        logger.error("Falha de conexão ao enviar Instagram para %s: %s", recipient_id, exc)
        raise
