"""Serviço de lembretes e pós-consulta — envios proativos via WhatsApp template."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from app.database import get_supabase_client
from app.services.meta_service import send_whatsapp_template

logger = logging.getLogger(__name__)

# Nomes dos templates aprovados na Meta (devem bater exatamente com o cadastrado)
_TEMPLATE_LEMBRETE = "lembrete_consulta"
_TEMPLATE_FOLLOWUP = "pos_consulta"


def _formatar_data(dt_str: str) -> str:
    """Converte ISO timestamp para formato legível em PT-BR."""
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y às %H:%Mh")
    except Exception:
        return dt_str


def _buscar_paciente_e_clinica(sb, clinic_id: str, patient_id: str, appt_id: str):
    """Retorna (patient, clinic) ou (None, None) logando o motivo."""
    pat_resp = (
        sb.table("patients")
        .select("phone, name")
        .eq("id", patient_id)
        .eq("clinic_id", clinic_id)
        .limit(1)
        .execute()
    )
    patient = (getattr(pat_resp, "data", None) or [None])[0]
    if not patient:
        logger.warning("Paciente %s não encontrado (appointment %s).", patient_id, appt_id)
        return None, None

    clinic_resp = (
        sb.table("clinics")
        .select("whatsapp_phone_number_id, name")
        .eq("id", clinic_id)
        .limit(1)
        .execute()
    )
    clinic = (getattr(clinic_resp, "data", None) or [None])[0]
    if not clinic or not clinic.get("whatsapp_phone_number_id"):
        logger.warning(
            "Clínica %s sem whatsapp_phone_number_id (appointment %s).", clinic_id, appt_id
        )
        return None, None

    return patient, clinic


def enviar_lembretes_pendentes() -> None:
    """
    Busca consultas na janela [agora+23h, agora+25h] com reminder_sent=false,
    envia template de lembrete e marca reminder_sent=true.
    Roda a cada hora via APScheduler.

    Template: lembrete_consulta
    Parâmetros: {{1}} nome, {{2}} procedimento, {{3}} data/hora, {{4}} clínica
    """
    sb = get_supabase_client()
    now = datetime.now(timezone.utc)
    janela_inicio = (now + timedelta(hours=23)).isoformat().replace("+00:00", "Z")
    janela_fim = (now + timedelta(hours=25)).isoformat().replace("+00:00", "Z")

    resp = (
        sb.table("appointments")
        .select("id, clinic_id, patient_id, datetime, procedure")
        .eq("reminder_sent", False)
        .gte("datetime", janela_inicio)
        .lte("datetime", janela_fim)
        .execute()
    )
    appointments = getattr(resp, "data", []) or []

    if not appointments:
        logger.debug("Lembretes: nenhum pendente na janela atual.")
        return

    logger.info("%d lembrete(s) a enviar.", len(appointments))

    for appt in appointments:
        appt_id = appt["id"]
        try:
            patient, clinic = _buscar_paciente_e_clinica(
                sb, appt["clinic_id"], appt["patient_id"], appt_id
            )
            if not patient or not clinic:
                continue

            send_whatsapp_template(
                phone_number_id=clinic["whatsapp_phone_number_id"],
                to=patient["phone"],
                template_name=_TEMPLATE_LEMBRETE,
                parameters=[
                    patient.get("name", "").split()[0] or "paciente",
                    appt.get("procedure", "consulta"),
                    _formatar_data(appt["datetime"]),
                    clinic["name"],
                ],
            )

            sb.table("appointments").update({"reminder_sent": True}).eq("id", appt_id).execute()
            logger.info("Lembrete enviado: appointment %s → %s", appt_id, patient["phone"])

        except Exception:
            logger.exception("Erro ao enviar lembrete (appointment %s).", appt_id)


def enviar_followup_pendentes() -> None:
    """
    Busca consultas que terminaram há entre 1h e 3h com followup_sent=false,
    envia template pós-consulta e marca followup_sent=true.
    Roda a cada hora via APScheduler.

    Template: pos_consulta
    Parâmetros: {{1}} nome, {{2}} procedimento
    """
    sb = get_supabase_client()
    now = datetime.now(timezone.utc)
    janela_inicio = (now - timedelta(hours=3)).isoformat().replace("+00:00", "Z")
    janela_fim = (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z")

    resp = (
        sb.table("appointments")
        .select("id, clinic_id, patient_id, datetime, procedure")
        .eq("followup_sent", False)
        .eq("status", "scheduled")
        .gte("datetime", janela_inicio)
        .lte("datetime", janela_fim)
        .execute()
    )
    appointments = getattr(resp, "data", []) or []

    if not appointments:
        logger.debug("Pós-consulta: nenhum pendente na janela atual.")
        return

    logger.info("%d pós-consulta(s) a enviar.", len(appointments))

    for appt in appointments:
        appt_id = appt["id"]
        try:
            patient, clinic = _buscar_paciente_e_clinica(
                sb, appt["clinic_id"], appt["patient_id"], appt_id
            )
            if not patient or not clinic:
                continue

            send_whatsapp_template(
                phone_number_id=clinic["whatsapp_phone_number_id"],
                to=patient["phone"],
                template_name=_TEMPLATE_FOLLOWUP,
                parameters=[
                    patient.get("name", "").split()[0] or "paciente",
                    appt.get("procedure", "consulta"),
                ],
            )

            sb.table("appointments").update({"followup_sent": True}).eq("id", appt_id).execute()
            logger.info("Pós-consulta enviado: appointment %s → %s", appt_id, patient["phone"])

        except Exception:
            logger.exception("Erro ao enviar pós-consulta (appointment %s).", appt_id)
