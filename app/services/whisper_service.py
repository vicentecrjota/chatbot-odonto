"""Transcrição de áudio via OpenAI Whisper."""

from __future__ import annotations

import io
import logging

import httpx
from openai import OpenAI

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_META_GRAPH_BASE = "https://graph.facebook.com/v19.0"
_MAX_AUDIO_BYTES = 10 * 1024 * 1024  # 10 MB
_TIMEOUT = 30.0


def _access_token() -> str:
    settings = get_settings()
    if not settings.meta_access_token:
        raise RuntimeError("META_ACCESS_TOKEN não configurado.")
    return settings.meta_access_token.get_secret_value()


def _baixar_audio_meta(media_id: str) -> tuple[bytes, str]:
    """
    1. Busca a URL do arquivo via /{media_id}
    2. Faz o download do binário de áudio
    Retorna (bytes, mime_type)
    """
    token = _access_token()
    headers = {"Authorization": f"Bearer {token}"}

    with httpx.Client(timeout=_TIMEOUT) as client:
        info_resp = client.get(f"{_META_GRAPH_BASE}/{media_id}", headers=headers)
        info_resp.raise_for_status()
        media_info = info_resp.json()

        url = media_info.get("url")
        mime_type = media_info.get("mime_type", "audio/ogg")
        if not url:
            raise RuntimeError(f"URL não retornada para media_id={media_id}")

        audio_resp = client.get(url, headers=headers)
        audio_resp.raise_for_status()

    audio_bytes = audio_resp.content
    if len(audio_bytes) > _MAX_AUDIO_BYTES:
        raise ValueError(
            f"Áudio muito grande: {len(audio_bytes)} bytes (máx {_MAX_AUDIO_BYTES})"
        )

    return audio_bytes, mime_type


def transcrever_audio(media_id: str) -> str:
    """
    Baixa o áudio do WhatsApp e transcreve via Whisper.
    Retorna o texto transcrito.
    """
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY não configurado.")

    audio_bytes, mime_type = _baixar_audio_meta(media_id)

    ext_map = {
        "audio/ogg": "ogg",
        "audio/mpeg": "mp3",
        "audio/mp4": "mp4",
        "audio/wav": "wav",
        "audio/webm": "webm",
        "audio/aac": "aac",
    }
    base_mime = mime_type.split(";")[0].strip()
    ext = ext_map.get(base_mime, "ogg")

    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = f"audio.{ext}"

    client = OpenAI(api_key=settings.openai_api_key.get_secret_value())
    transcript = client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
        language="pt",
    )

    text = transcript.text.strip()
    logger.info("Áudio transcrito (%d bytes): %.100s", len(audio_bytes), text)
    return text
