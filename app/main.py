"""Ponto de entrada da API (FastAPI)."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.auth import router as auth_router
from app.api.clinics import router as clinics_router
from app.api.dashboard import router as dashboard_router
from app.api.health import router as health_router
from app.api.lgpd import router as lgpd_router
from app.api.webhooks import router as webhooks_router
from app.services.cleanup_service import limpar_conversas_expiradas
from app.services.reminder_service import enviar_followup_pendentes, enviar_lembretes_pendentes

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


@asynccontextmanager
async def lifespan(application: FastAPI):  # type: ignore[type-arg]
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        enviar_lembretes_pendentes,
        trigger="interval",
        hours=1,
        id="reminders",
        replace_existing=True,
    )
    scheduler.add_job(
        enviar_followup_pendentes,
        trigger="interval",
        hours=1,
        id="followup",
        replace_existing=True,
    )
    scheduler.add_job(
        limpar_conversas_expiradas,
        trigger="interval",
        hours=24,
        id="cleanup",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler de lembretes iniciado (intervalo: 1h).")
    yield
    scheduler.shutdown(wait=False)
    logger.info("Scheduler de lembretes encerrado.")


def create_app() -> FastAPI:
    application = FastAPI(
        title="chatbot-odonto",
        version=_APP_VERSION,
        lifespan=lifespan,
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
    application.include_router(auth_router)
    application.include_router(clinics_router)
    application.include_router(dashboard_router)
    application.include_router(lgpd_router)

    return application


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = create_app()
