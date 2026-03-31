"""Conformidade LGPD — consentimento explícito na primeira interação."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.database import get_supabase_client

logger = logging.getLogger(__name__)

_MENSAGEM_CONSENTIMENTO = (
    "Olá! Antes de começarmos, preciso da sua autorização. 😊\n\n"
    "Para te atender, vou armazenar seus dados (telefone e informações fornecidas "
    "durante a conversa) conforme a Lei Geral de Proteção de Dados (LGPD).\n\n"
    "Os dados são usados exclusivamente para agendamentos e atendimento nesta clínica, "
    "e você pode solicitar acesso, correção ou exclusão a qualquer momento.\n\n"
    "*Você aceita os termos acima?* Responda *SIM* para continuar."
)

_AGUARDANDO_RESPOSTA = (
    "Para continuar, preciso da sua confirmação. "
    "Responda *SIM* para aceitar os termos e iniciar o atendimento."
)

_CONSENTIMENTO_RECUSADO = (
    "Sem problemas! Seus dados não serão armazenados. "
    "Se mudar de ideia, é só entrar em contato novamente. Até logo! 😊"
)

_SIM_KEYWORDS = {"sim", "s", "aceito", "concordo", "ok", "yes", "pode", "claro", "tudo bem"}
_NAO_KEYWORDS = {"não", "nao", "n", "recuso", "no", "nunca", "negativo"}


def _normalizar(texto: str) -> str:
    return texto.lower().strip().rstrip(".")


def _e_sim(texto: str) -> bool:
    return _normalizar(texto) in _SIM_KEYWORDS


def _e_nao(texto: str) -> bool:
    return _normalizar(texto) in _NAO_KEYWORDS


def _buscar_paciente(phone: str, clinic_id: str) -> dict | None:
    sb = get_supabase_client()
    resp = (
        sb.table("patients")
        .select("id, consent_given, consent_at, metadata")
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

    # Paciente já aceitou → segue normalmente
    if paciente and paciente.get("consent_given"):
        return True, None

    # Paciente existe mas ainda não respondeu ao consentimento
    if paciente:
        patient_id = paciente["id"]

        if _e_sim(message):
            _registrar_consentimento(patient_id, True)
            return True, None  # deixa o pipeline processar a mensagem normalmente

        if _e_nao(message):
            _registrar_consentimento(patient_id, False)
            return False, _CONSENTIMENTO_RECUSADO

        # Resposta não reconhecida — repete o pedido
        return False, _AGUARDANDO_RESPOSTA

    # Primeira vez que este paciente contata a clínica → cria registro e envia consentimento
    _criar_paciente(phone, clinic_id)
    return False, _MENSAGEM_CONSENTIMENTO
