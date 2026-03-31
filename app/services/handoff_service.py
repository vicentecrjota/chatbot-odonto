"""Detecção de gatilhos de handoff e gerenciamento de transferência para humano."""

from __future__ import annotations

import logging
import re

from app.database import get_supabase_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Gatilho 1 — Pedido explícito do paciente
# ---------------------------------------------------------------------------
_EXPLICIT_KEYWORDS = [
    "falar com atendente",
    "falar com humano",
    "falar com uma pessoa",
    "falar com alguém",
    "quero atendente",
    "quero humano",
    "preciso de atendente",
    "me passa para atendente",
    "atendimento humano",
    "chamar atendente",
    "pessoa real",
    "não quero falar com bot",
    "não quero falar com robô",
    "quero falar com o dentista",
    "falar com a recepção",
    "falar com a secretaria",
]

# ---------------------------------------------------------------------------
# Gatilho 5 — Cenário complexo (convênio, reclamação, jurídico)
# ---------------------------------------------------------------------------
_COMPLEX_KEYWORDS = [
    "convênio",
    "plano odontológico",
    "reembolso",
    "reclamação",
    "processo",
    "advogado",
    "procon",
    "erro médico",
    "negligência",
    "cobrança indevida",
    "cobrou errado",
    "estou processando",
]


def _normalizar(texto: str) -> str:
    return texto.lower().strip()


def checar_pedido_explicito(message: str) -> bool:
    """Gatilho 1: paciente pediu explicitamente para falar com humano."""
    msg = _normalizar(message)
    return any(kw in msg for kw in _EXPLICIT_KEYWORDS)


def checar_cenario_complexo(message: str) -> bool:
    """Gatilho 5: mensagem envolve cenário complexo (convênio, reclamação, jurídico)."""
    msg = _normalizar(message)
    return any(kw in msg for kw in _COMPLEX_KEYWORDS)


def checar_loop(historico: list[dict]) -> bool:
    """
    Gatilho 6: detecta loop — mais de 8 mensagens do usuário sem resolução.
    Critério simples: se o histórico tiver 8+ mensagens de usuário, considera loop.
    O LLM é o principal detector de loops via tag [TRANSFERIR]; este é o safety net.
    """
    user_msgs = [m for m in historico if m.get("role") == "user"]
    return len(user_msgs) >= 8


# ---------------------------------------------------------------------------
# Estado da conversa no banco
# ---------------------------------------------------------------------------

def esta_em_handoff(phone: str, clinic_id: str) -> bool:
    """Verifica se a conversa já está em modo human_takeover."""
    sb = get_supabase_client()
    resp = (
        sb.table("conversations")
        .select("status")
        .eq("clinic_id", clinic_id)
        .eq("patient_phone", phone)
        .limit(1)
        .execute()
    )
    data = getattr(resp, "data", None)
    if not data or not isinstance(data, list) or not data[0]:
        return False
    return data[0].get("status") == "human_takeover"


def marcar_handoff(phone: str, clinic_id: str, gatilho: str) -> None:
    """Marca a conversa como human_takeover no banco."""
    sb = get_supabase_client()
    try:
        sb.table("conversations").update({"status": "human_takeover"}).eq(
            "clinic_id", clinic_id
        ).eq("patient_phone", phone).execute()
        logger.info(
            "Handoff marcado: phone=%s clinic_id=%s gatilho=%s",
            phone, clinic_id, gatilho,
        )
    except Exception:
        logger.exception("Erro ao marcar handoff para phone=%s", phone)


# ---------------------------------------------------------------------------
# Helpers para parsear tag [TRANSFERIR] do LLM
# ---------------------------------------------------------------------------

_TRANSFERIR_RE = re.compile(r"\[TRANSFERIR:([^\]]*)\]", re.IGNORECASE)


def extrair_tag_transferir(resposta: str) -> tuple[bool, str, str]:
    """
    Verifica se a resposta do LLM contém a tag [TRANSFERIR:motivo].
    Retorna (transferir: bool, motivo: str, resposta_limpa: str).
    """
    match = _TRANSFERIR_RE.search(resposta)
    if not match:
        return False, "", resposta
    motivo = match.group(1).strip()
    resposta_limpa = _TRANSFERIR_RE.sub("", resposta).strip()
    return True, motivo, resposta_limpa
