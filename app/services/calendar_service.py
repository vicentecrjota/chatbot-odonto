"""Integração com Google Calendar para busca de slots e criação de eventos."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from google.oauth2 import service_account
from googleapiclient.discovery import build

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/calendar"]
_SLOT_DURATION_MINUTES = 60
_SEARCH_DAYS_AHEAD = 14
_BUSINESS_HOUR_START = 8
_BUSINESS_HOUR_END = 18


def _get_service():
    settings = get_settings()
    if not settings.google_credentials:
        raise RuntimeError("GOOGLE_CREDENTIALS não configurado.")
    creds_info = json.loads(settings.google_credentials)
    creds = service_account.Credentials.from_service_account_info(
        creds_info, scopes=_SCOPES
    )
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def _candidate_slots(timezone: str, days_ahead: int) -> list[datetime]:
    """Gera lista de horários candidatos em dias úteis dentro do horário comercial."""
    tz = ZoneInfo(timezone)
    now = datetime.now(tz=tz)
    slots = []
    day = now.date()
    while len(slots) < days_ahead * 10:
        # Pula finais de semana
        if day.weekday() < 5:
            for hour in range(_BUSINESS_HOUR_START, _BUSINESS_HOUR_END):
                candidate = datetime(day.year, day.month, day.day, hour, 0, tzinfo=tz)
                if candidate > now + timedelta(hours=1):
                    slots.append(candidate)
        day += timedelta(days=1)
    return slots


def buscar_slots_disponiveis(
    calendar_id: str,
    timezone: str = "America/Sao_Paulo",
    num_slots: int = 2,
) -> list[dict[str, str]]:
    """
    Retorna os próximos N slots livres no calendário da clínica.
    Cada slot: {"start": "2025-04-01T09:00", "end": "2025-04-01T10:00", "label": "Terça, 01/04 às 09:00"}
    """
    service = _get_service()
    tz = ZoneInfo(timezone)
    now = datetime.now(tz=tz)
    time_max = now + timedelta(days=_SEARCH_DAYS_AHEAD)

    # Busca eventos já existentes no período
    events_result = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=now.isoformat(),
            timeMax=time_max.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    busy_intervals = []
    for event in events_result.get("items", []):
        start = event.get("start", {}).get("dateTime")
        end = event.get("end", {}).get("dateTime")
        if start and end:
            busy_intervals.append(
                (datetime.fromisoformat(start), datetime.fromisoformat(end))
            )

    candidates = _candidate_slots(timezone, _SEARCH_DAYS_AHEAD)
    free_slots = []
    for slot_start in candidates:
        slot_end = slot_start + timedelta(minutes=_SLOT_DURATION_MINUTES)
        overlap = any(
            not (slot_end <= b_start or slot_start >= b_end)
            for b_start, b_end in busy_intervals
        )
        if not overlap:
            weekdays = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
            label = f"{weekdays[slot_start.weekday()]}, {slot_start.strftime('%d/%m')} às {slot_start.strftime('%H:%M')}"
            free_slots.append(
                {
                    "start": slot_start.isoformat(),
                    "end": slot_end.isoformat(),
                    "label": label,
                }
            )
            if len(free_slots) >= num_slots:
                break

    return free_slots


def criar_evento(
    calendar_id: str,
    start_iso: str,
    end_iso: str,
    procedure: str,
    patient_phone: str,
    timezone: str = "America/Sao_Paulo",
) -> str:
    """Cria evento no Google Calendar e retorna o link."""
    service = _get_service()
    event: dict[str, Any] = {
        "summary": f"Consulta — {procedure}",
        "description": f"Paciente: {patient_phone}\nProcedimento: {procedure}",
        "start": {"dateTime": start_iso, "timeZone": timezone},
        "end": {"dateTime": end_iso, "timeZone": timezone},
    }
    created = service.events().insert(calendarId=calendar_id, body=event).execute()
    return created.get("htmlLink", "")
