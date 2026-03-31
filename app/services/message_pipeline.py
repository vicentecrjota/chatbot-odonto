"""Pipeline principal de atendimento (mensagens -> resposta)."""

from __future__ import annotations

from datetime import datetime, time as dtime
from typing import Any

from app.database import get_supabase_client
from app.prompts.base_prompt import montar_prompt
from app.services.calendar_service import buscar_slots_disponiveis, criar_evento
from app.services.conversation_service import carregar_historico, salvar_mensagens
from app.services.llm_service import chamar_llm
from app.services.handoff_service import (
    checar_cenario_complexo,
    checar_loop,
    checar_pedido_explicito,
    esta_em_handoff,
    extrair_tag_transferir,
    marcar_handoff,
)
from app.services.patient_service import atualizar_contexto_paciente, carregar_contexto_paciente
from app.services.rag_service import RagServiceError, buscar_documentos


def _clinic_from_supabase(clinic_id: str) -> dict[str, Any]:
    sb = get_supabase_client()
    resp = sb.table("clinics").select("*").eq("id", clinic_id).limit(1).execute()
    data = getattr(resp, "data", None)
    if not data:
        raise RuntimeError("Clínica não encontrada no Supabase.")
    if not isinstance(data, list) or not isinstance(data[0], dict):
        raise RuntimeError("Resposta inesperada ao buscar clínica no Supabase.")
    return data[0]


def _parse_business_hours(value: Any) -> dict[str, Any] | None:
    """
    Suporta um formato simples:
      {"timezone": "America/Sao_Paulo", "open": "09:00", "close": "18:00"}
    ou
      {"open": "09:00", "close": "18:00"}
    """
    if not isinstance(value, dict):
        return None
    if "open" in value and "close" in value:
        return value
    return None


def _within_business_hours(clinic: dict[str, Any]) -> bool:
    """
    Se houver configuração estruturada em `rag_config.business_hours`, valida.
    Se não houver, retorna True (não bloqueia atendimento).
    """
    rag_config = clinic.get("rag_config")
    hours_cfg = None
    if isinstance(rag_config, dict):
        hours_cfg = _parse_business_hours(rag_config.get("business_hours"))

    if not hours_cfg:
        return True

    # Timezone é opcional; se ausente, usa horário local do servidor.
    tz_name = hours_cfg.get("timezone")
    now = datetime.now()
    if tz_name:
        try:
            from zoneinfo import ZoneInfo

            now = datetime.now(tz=ZoneInfo(str(tz_name)))
        except Exception:
            # fallback: mantém horário local
            pass

    def _to_time(s: Any) -> dtime | None:
        if not isinstance(s, str):
            return None
        try:
            hh, mm = s.split(":")
            return dtime(hour=int(hh), minute=int(mm))
        except Exception:
            return None

    open_t = _to_time(hours_cfg.get("open"))
    close_t = _to_time(hours_cfg.get("close"))
    if not open_t or not close_t:
        return True

    now_t = now.timetz().replace(tzinfo=None)
    if open_t <= close_t:
        return open_t <= now_t <= close_t

    # Caso em que o horário atravessa meia-noite (ex.: 22:00-06:00)
    return now_t >= open_t or now_t <= close_t


def processar_mensagem(phone: str, message: str, clinic_id: str) -> str:
    """
    Pipeline:
    1) Busca dados da clínica no Supabase
    2) Verifica horário de atendimento
    3) Busca documentos (RAG)
    4) Chama o LLM e retorna a resposta em texto
    """

    clinic = _clinic_from_supabase(clinic_id)
    clinic_name = clinic.get("name") or "a clínica"

    # --- Verificação: conversa já está em handoff? ---
    if esta_em_handoff(phone, clinic_id):
        return (
            "Sua conversa já está com um dos nossos atendentes. "
            "Em breve alguém irá te responder. Se for urgência, ligue diretamente para a clínica."
        )

    # --- Gatilhos pré-LLM (keyword-based) ---
    if checar_pedido_explicito(message):
        marcar_handoff(phone, clinic_id, "pedido_explicito")
        salvar_mensagens(phone, clinic_id, message,
            "Claro! Vou te encaminhar para um dos nossos atendentes agora. Em breve alguém irá te responder.")
        return "Claro! Vou te encaminhar para um dos nossos atendentes agora. Em breve alguém irá te responder."

    if checar_cenario_complexo(message):
        marcar_handoff(phone, clinic_id, "cenario_complexo")
        salvar_mensagens(phone, clinic_id, message,
            "Entendi! Esse assunto precisa de atenção especial. Vou te encaminhar para um dos nossos atendentes que poderá te ajudar melhor.")
        return "Entendi! Esse assunto precisa de atenção especial. Vou te encaminhar para um dos nossos atendentes que poderá te ajudar melhor."

    if not _within_business_hours(clinic):
        return (
            f"Olá! No momento estamos fora do horário de atendimento da {clinic_name}. "
            "Posso registrar sua mensagem para a equipe humana retornar assim que possível? "
            "Se for emergência (dor intensa, sangramento persistente, trauma), procure pronto-socorro/UPA."
        )

    docs_text = ""
    try:
        docs = buscar_documentos(clinic_id, message)
        if docs:
            joined = "\n\n".join(f"- {d.get('content','')}".strip() for d in docs if d.get("content"))
            if joined.strip():
                docs_text = (
                    "\n\n## Contexto (documentos internos da clínica)\n"
                    "Use o contexto abaixo apenas se for relevante. Não invente nada além dele.\n"
                    f"{joined}\n"
                )
    except RagServiceError:
        # Se o RAG não estiver configurado (DATABASE_URL/OPENAI), seguimos sem contexto.
        docs_text = ""

    contexto_paciente = carregar_contexto_paciente(phone, clinic_id)
    contexto_text = ""
    if contexto_paciente:
        linhas = "\n".join(f"- {k}: {v}" for k, v in contexto_paciente.items())
        contexto_text = f"\n\n## Contexto do paciente\n{linhas}\n"

    # Busca slots do Google Calendar se a clínica tiver calendário configurado
    slots_text = ""
    calendar_id = clinic.get("google_calendar_id")
    if calendar_id:
        try:
            tz = "America/Sao_Paulo"
            rag_config = clinic.get("rag_config") or {}
            if isinstance(rag_config, dict):
                tz = rag_config.get("business_hours", {}).get("timezone", tz)
            slots = buscar_slots_disponiveis(calendar_id, timezone=tz, num_slots=2)
            if slots:
                opcoes = "\n".join(f"- Opção {i+1}: {s['label']} (start={s['start']}, end={s['end']})" for i, s in enumerate(slots))
                slots_text = (
                    "\n\n## Horários disponíveis (próximos slots livres)\n"
                    "Use estes horários ao oferecer opções de agendamento. "
                    "Quando o paciente confirmar um, use o start e end para criar o evento.\n"
                    f"{opcoes}\n"
                )
        except Exception:
            pass  # Segue sem slots se o calendário falhar

    system_prompt = montar_prompt(clinic) + contexto_text + slots_text + docs_text

    historico = carregar_historico(phone, clinic_id)

    # --- Gatilho 6: loop detectado (safety net) ---
    if checar_loop(historico):
        marcar_handoff(phone, clinic_id, "loop_detectado")
        salvar_mensagens(phone, clinic_id, message,
            "Percebi que estamos em uma conversa longa e quero garantir que você seja bem atendido(a). Vou te encaminhar para um dos nossos atendentes agora.")
        return "Percebi que estamos em uma conversa longa e quero garantir que você seja bem atendido(a). Vou te encaminhar para um dos nossos atendentes agora."

    history = historico + [
        {"role": "user", "content": message},
    ]

    resposta = chamar_llm(system_prompt, history)

    # --- Gatilhos via LLM: parse da tag [TRANSFERIR] ---
    transferir, motivo, resposta = extrair_tag_transferir(resposta)
    if transferir:
        marcar_handoff(phone, clinic_id, motivo or "llm_detectado")

    # Se o LLM confirmou agendamento, tenta criar o evento
    if calendar_id and "[AGENDAR:" in resposta:
        try:
            import re
            m = re.search(r"\[AGENDAR:([^|]+)\|([^|]+)\|([^\]]+)\]", resposta)
            if m:
                start_iso, end_iso, procedure = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
                criar_evento(calendar_id, start_iso, end_iso, procedure, phone, tz)
                resposta = re.sub(r"\[AGENDAR:[^\]]+\]", "", resposta).strip()
        except Exception:
            pass

    salvar_mensagens(phone, clinic_id, message, resposta)
    atualizar_contexto_paciente(phone, clinic_id, message, resposta)
    return resposta

