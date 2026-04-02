"""Conformidade LGPD — consentimento explícito na primeira interação."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.database import get_supabase_client
from app.services.patient_service import (
    AWAITING_PATIENT_NAME_METADATA_KEY,
    marcar_aguardando_nome_apos_lgpd,
    salvar_nome_apos_consentimento_lgpd,
)

logger = logging.getLogger(__name__)

_MENSAGEM_CONSENTIMENTO = (
    "Oi! 👋 Pra eu te ajudar por aqui, preciso só confirmar uma coisa rapidinho.\n\n"
    "Vou usar seu número e o que você mandar na conversa para agendar e te atender direitinho, "
    "seguindo a Lei Geral de Proteção de Dados (LGPD). É só para essa clínica — e se quiser ver, "
    "corrigir ou apagar seus dados, é só pedir.\n\n"
    "*Beleza pra gente continuar?* Me manda um *SIM* que já começamos! 😊"
)

_AGUARDANDO_RESPOSTA = (
    "Só falta esse ok 😊 Responde *SIM* pra aceitar e a gente segue com o atendimento por aqui."
)

_CONSENTIMENTO_RECUSADO = (
    "Tranquilo! Não vou guardar seus dados. Se mudar de ideia, chama de novo quando quiser. Até! 😊"
)

_PERGUNTA_NOME = "Ótimo! Para te atender melhor, qual é o seu nome? 😊"

_NOME_VAZIO_OU_CURTO = (
    "Me diz como posso te chamar? Pode ser só o primeiro nome. 😊"
)

_PERGUNTA_NOME_NOVAMENTE = (
    "Qual é o seu nome, pra eu te chamar certinho? 😊"
)

_SIM_KEYWORDS = {"sim", "s", "aceito", "concordo", "ok", "yes", "pode", "claro", "tudo bem"}
_NAO_KEYWORDS = {"não", "nao", "n", "recuso", "no", "nunca", "negativo"}


def _normalizar(texto: str) -> str:
    return texto.lower().strip().rstrip(".")


def _e_sim(texto: str) -> bool:
    return _normalizar(texto) in _SIM_KEYWORDS


def _e_nao(texto: str) -> bool:
    return _normalizar(texto) in _NAO_KEYWORDS


def _metadata_dict(raw: Any) -> dict:
    if isinstance(raw, dict):
        return raw
    return {}


def _buscar_paciente(phone: str, clinic_id: str) -> dict | None:
    sb = get_supabase_client()
    resp = (
        sb.table("patients")
        .select("id, consent_given, consent_at, metadata, name")
        .eq("clinic_id", clinic_id)
        .eq("phone", phone)
        .limit(1)
        .execute()
    )
    data = getattr(resp, "data", None)
    if data and isinstance(data, list) and data[0]:
        return data[0]
    return None


def _criar_paciente(phone: str, clinic_id: str) -> str | None:
    sb = get_supabase_client()
    resp = (
        sb.table("patients")
        .insert({"clinic_id": clinic_id, "phone": phone, "name": phone, "consent_given": False})
        .execute()
    )
    data = getattr(resp, "data", None)
    if data and isinstance(data, list) and data[0]:
        return data[0]["id"]
    return None


def _registrar_consentimento(patient_id: str, dado: bool) -> None:
    sb = get_supabase_client()
    sb.table("patients").update({
        "consent_given": dado,
        "consent_at": datetime.now(tz=timezone.utc).isoformat(),
    }).eq("id", patient_id).execute()
    logger.info("Consentimento registrado: patient_id=%s aceito=%s", patient_id, dado)


def verificar_consentimento(phone: str, clinic_id: str, message: str) -> tuple[bool, str | None]:
    """
    Verifica e gerencia o fluxo de consentimento LGPD.

    Retorna:
        (pode_processar: bool, resposta_lgpd: str | None)

    - Se pode_processar=True  → segue normalmente para o pipeline
    - Se pode_processar=False → retorna resposta_lgpd ao paciente e para o processamento
    """
    paciente = _buscar_paciente(phone, clinic_id)

    if paciente and paciente.get("consent_given"):
        meta = _metadata_dict(paciente.get("metadata"))
        if meta.get(AWAITING_PATIENT_NAME_METADATA_KEY):
            texto = message.strip()
            if len(texto) < 2:
                return False, _NOME_VAZIO_OU_CURTO
            if _e_sim(texto) or _e_nao(texto):
                return False, _PERGUNTA_NOME_NOVAMENTE
            salvar_nome_apos_consentimento_lgpd(paciente["id"], texto)
            return True, None
        return True, None

    if paciente:
        patient_id = paciente["id"]

        if _e_sim(message):
            _registrar_consentimento(patient_id, True)
            marcar_aguardando_nome_apos_lgpd(patient_id)
            return False, _PERGUNTA_NOME

        if _e_nao(message):
            _registrar_consentimento(patient_id, False)
            return False, _CONSENTIMENTO_RECUSADO

        return False, _AGUARDANDO_RESPOSTA

    _criar_paciente(phone, clinic_id)
    return False, _MENSAGEM_CONSENTIMENTO
