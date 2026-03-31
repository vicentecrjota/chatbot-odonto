"""Serviço de lembretes automáticos — envia WhatsApp 24h antes da consulta."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.database import get_supabase_client
from app.services.meta_service import send_whatsapp_message

logger = logging.getLogger(__name__)


def _formatar_data(dt_str: str) -> str:
    """Converte ISO timestamp para formato legível em PT-BR."""
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        # Exibe no horário UTC; clinica pode ajustar timezone no futuro.
        return dt.strftime("%d/%m/%Y às %H:%Mh")
    except Exception:
        return dt_str


def enviar_lembretes_pendentes() -> None:
    """
    Busca consultas agendadas na janela [agora+23h, agora+25h] com reminder_sent=false,
    envia lembrete via WhatsApp e marca reminder_sent=true.

    Projetado para rodar a cada hora via APScheduler.
    """
    sb = get_supabase_client()

    # Janela de 23h a 25h a partir de agora (UTC).
    # Supabase aceita ISO 8601 com timezone.
    now = datetime.now(timezone.utc)
    window_start = now.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    window_end_dt = now.replace(microsecond=0)

    from datetime import timedelta
    janela_inicio = (now + timedelta(hours=23)).isoformat().replace("+00:00", "Z")
    janela_fim = (now + timedelta(hours=25)).isoformat().replace("+00:00", "Z")

    # Busca appointments na janela sem lembrete enviado.
    # JOIN manual: appointments → patients → clinics via Python (Supabase JS SDK não suporta JOIN nativo).
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
        logger.debug("Nenhum lembrete pendente na janela atual.")
        return

    logger.info("%d lembrete(s) a enviar.", len(appointments))

    for appt in appointments:
        appt_id = appt["id"]
        clinic_id = appt["clinic_id"]
        patient_id = appt["patient_id"]
        appt_datetime = appt["datetime"]
        procedure = appt.get("procedure", "consulta")

        try:
            # Busca telefone do paciente.
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
                logger.warning("Paciente %s não encontrado para appointment %s.", patient_id, appt_id)
                continue

            # Busca phone_number_id da clínica para enviar a mensagem.
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
                    "Clínica %s sem whatsapp_phone_number_id — lembrete não enviado para appointment %s.",
                    clinic_id,
                    appt_id,
                )
                continue

            phone_number_id = clinic["whatsapp_phone_number_id"]
            patient_phone = patient["phone"]
            patient_name = patient.get("name", "")
            clinic_name = clinic.get("name", "a clínica")
            data_formatada = _formatar_data(appt_datetime)

            mensagem = (
                f"Olá{', ' + patient_name.split()[0] if patient_name else ''}! "
                f"Lembramos que você tem uma consulta de *{procedure}* agendada para "
                f"*{data_formatada}* em {clinic_name}. "
                f"Caso precise remarcar, entre em contato com a gente. Até logo!"
            )

            send_whatsapp_message(phone_number_id, patient_phone, mensagem)

            # Marca lembrete como enviado.
            sb.table("appointments").update({"reminder_sent": True}).eq("id", appt_id).execute()
            logger.info("Lembrete enviado para %s (appointment %s).", patient_phone, appt_id)

        except Exception as exc:
            # Não interrompe o loop — outros pacientes devem continuar recebendo.
            logger.error("Erro ao enviar lembrete para appointment %s: %s", appt_id, exc)
