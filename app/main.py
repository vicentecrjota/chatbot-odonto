"""Ponto de entrada da API (FastAPI)."""

from __future__ import annotations

import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.clinics import router as clinics_router
from app.api.health import router as health_router
from app.api.webhooks import router as webhooks_router

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

    application.include_router(health_router, tags=["Health"])
    application.include_router(webhooks_router, tags=["Webhooks"])
    application.include_router(clinics_router)

    return application


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = create_app()
