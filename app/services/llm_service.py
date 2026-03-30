"""Integração com a API de LLM (OpenAI)."""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.core.config import get_settings


class LlmTimeoutError(RuntimeError):
    """Falha por timeout ao chamar o LLM."""


class LlmRateLimitError(RuntimeError):
    """Rate limit (HTTP 429) ao chamar o LLM."""


def chamar_llm(
    system_prompt: str,
    history: list[dict[str, str]],
    *,
    model: str = "gpt-4o-mini",
    timeout_seconds: float = 30.0,
    max_retries: int = 2,
) -> str:
    """
    Chama o modelo configurado (default: gpt-4o-mini).

    Parameters
    ----------
    system_prompt:
        Prompt do sistema.
    history:
        Histórico da conversa no formato: [{"role": "...", "content": "..."}].
    """

    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY não configurada no Settings.")

    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}, *history]

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key.get_secret_value()}",
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
    }

    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            with httpx.Client(timeout=httpx.Timeout(timeout_seconds)) as client:
                resp = client.post(url, headers=headers, json=payload)

            # Rate limit: tenta novamente respeitando Retry-After quando possível.
            if resp.status_code == 429:
                retry_after_raw = resp.headers.get("Retry-After")
                retry_after_s: float | None = None
                if retry_after_raw:
                    try:
                        retry_after_s = float(retry_after_raw)
                    except ValueError:
                        retry_after_s = None

                if attempt >= max_retries:
                    raise LlmRateLimitError(
                        "Rate limit ao chamar LLM (HTTP 429)."
                    )

                backoff = retry_after_s if retry_after_s is not None else (2**attempt)
                time.sleep(backoff)
                continue

            # Erros HTTP genéricos.
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise RuntimeError("Resposta do LLM sem campo de texto esperado.")
            return content

        except httpx.TimeoutException as e:
            last_error = e
            if attempt >= max_retries:
                raise LlmTimeoutError("Timeout ao chamar LLM.") from e
            time.sleep(2**attempt)
            continue
        except (httpx.HTTPError, ValueError) as e:
            # Não é pedido re-tentar para todos os erros; falha imediata com contexto.
            raise RuntimeError(f"Erro ao chamar LLM: {e}") from e

    # Por segurança (should not happen).
    if last_error:
        raise RuntimeError("Falha ao chamar LLM.") from last_error
    raise RuntimeError("Falha ao chamar LLM por motivo desconhecido.")

