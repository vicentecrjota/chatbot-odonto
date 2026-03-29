"""Ponto de entrada da API (FastAPI)."""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings

logger = logging.getLogger("chatbot_odonto.http")

_APP_VERSION = "1.0.0"


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "%s %s -> %s (%.2f ms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="chatbot-odonto",
        version=_APP_VERSION,
    )

    application.add_middleware(RequestLoggingMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": _APP_VERSION}

    @application.get("/webhook/whatsapp", response_class=PlainTextResponse)
    def whatsapp_webhook_verify(
        hub_mode: str | None = Query(None, alias="hub.mode"),
        hub_verify_token: str | None = Query(None, alias="hub.verify_token"),
        hub_challenge: str | None = Query(None, alias="hub.challenge"),
    ) -> PlainTextResponse:
        if hub_mode != "subscribe" or hub_challenge is None:
            raise HTTPException(status_code=400, detail="Invalid verification request")
        if hub_verify_token != settings.meta_verify_token:
            raise HTTPException(status_code=403, detail="Forbidden")
        return PlainTextResponse(content=hub_challenge)

    @application.post("/webhook/whatsapp")
    async def whatsapp_webhook(payload: dict[str, Any]) -> dict[str, str]:
        _ = payload
        return {"status": "ok"}

    @application.post("/webhook/instagram")
    async def instagram_webhook(payload: dict[str, Any]) -> dict[str, str]:
        _ = payload
        return {"status": "ok"}

    return application


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = create_app()
