"""Sistema de busca RAG (pgvector) para documentos de clínicas."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Iterable

import httpx
import psycopg
import tiktoken

from app.core.config import get_settings

OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536
CHUNK_TOKENS = 400


class RagServiceError(RuntimeError):
    pass


def _tokenizer() -> tiktoken.Encoding:
    # Para embeddings, o modelo costuma usar a mesma base do `cl100k_base`.
    try:
        return tiktoken.encoding_for_model(OPENAI_EMBEDDING_MODEL)
    except Exception:
        return tiktoken.get_encoding("cl100k_base")


def _chunk_text_by_tokens(texto: str, tokens_por_chunk: int = CHUNK_TOKENS) -> list[str]:
    enc = _tokenizer()
    token_ids = enc.encode(texto)
    if not token_ids:
        return []

    chunks: list[str] = []
    for i in range(0, len(token_ids), tokens_por_chunk):
        chunk_ids = token_ids[i : i + tokens_por_chunk]
        chunks.append(enc.decode(chunk_ids))
    return chunks


def gerar_embedding(texto: str, *, timeout_seconds: float = 30.0) -> list[float]:
    """Gera embedding do texto via OpenAI (model `text-embedding-3-small`)."""

    settings = get_settings()
    if not settings.openai_api_key:
        raise RagServiceError("OPENAI_API_KEY não configurada.")

    url = "https://api.openai.com/v1/embeddings"
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key.get_secret_value()}",
        "Content-Type": "application/json",
    }
    payload = {"model": OPENAI_EMBEDDING_MODEL, "input": texto}

    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with httpx.Client(timeout=httpx.Timeout(timeout_seconds)) as client:
                resp = client.post(url, headers=headers, json=payload)

            if resp.status_code == 429:
                retry_after_raw = resp.headers.get("Retry-After")
                retry_after_s = None
                if retry_after_raw:
                    try:
                        retry_after_s = float(retry_after_raw)
                    except ValueError:
                        retry_after_s = None
                if attempt >= 2:
                    raise RagServiceError("Rate limit ao gerar embedding (HTTP 429).")
                time.sleep(retry_after_s if retry_after_s is not None else (2**attempt))
                continue

            resp.raise_for_status()
            data = resp.json()
            embedding = data["data"][0]["embedding"]
            if not isinstance(embedding, list):
                raise RagServiceError("Resposta do OpenAI sem embedding em formato esperado.")

            # Garantia defensiva para compatibilidade com `vector(1536)`.
            if len(embedding) != EMBEDDING_DIM:
                raise RagServiceError(f"Dimensão do embedding inesperada: {len(embedding)}.")
            return [float(x) for x in embedding]

        except httpx.TimeoutException as e:
            last_error = e
            if attempt >= 2:
                raise RagServiceError("Timeout ao gerar embedding.") from e
            time.sleep(2**attempt)

    if last_error:
        raise RagServiceError("Falha ao gerar embedding.") from last_error
    raise RagServiceError("Falha ao gerar embedding por motivo desconhecido.")


def _vector_literal(embedding: list[float]) -> str:
    # pgvector aceita string literal tipo: [0.1,0.2,...]::vector
    return "[" + ",".join(f"{x:.10f}" for x in embedding) + "]"


def buscar_documentos(clinic_id: str, pergunta: str) -> list[dict[str, Any]]:
    """
    Busca os 5 chunks mais relevantes usando pgvector,
    filtrando por `clinic_id`.
    """

    settings = get_settings()
    if not settings.database_url:
        raise RagServiceError("DATABASE_URL não configurada.")

    query_embedding = gerar_embedding(pergunta)
    qvec = _vector_literal(query_embedding)

    sql = """
        SELECT
            id,
            content,
            metadata,
            (embedding <=> %s::vector) AS distance
        FROM rag_documents
        WHERE clinic_id = %s
        ORDER BY embedding <=> %s::vector ASC
        LIMIT 5;
    """

    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            # Garante isolamento multi-tenant via RLS.
            cur.execute("SET LOCAL app.current_clinic_id = %s;", (clinic_id,))
            cur.execute(sql, (qvec, clinic_id, qvec))
            rows = cur.fetchall()

    # distance menor = mais similar (cosine distance).
    return rows


def indexar_documento(clinic_id: str, texto: str) -> int:
    """
    Divide o texto em chunks de ~400 tokens, gera embeddings e salva no banco.
    Retorna o número de chunks inseridos.
    """

    settings = get_settings()
    if not settings.database_url:
        raise RagServiceError("DATABASE_URL não configurada.")

    chunks = _chunk_text_by_tokens(texto, CHUNK_TOKENS)
    if not chunks:
        return 0

    insert_sql = """
        INSERT INTO rag_documents (clinic_id, content, embedding, metadata)
        VALUES (%s, %s, %s::vector, %s::jsonb);
    """

    inserted = 0
    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            # Garante isolamento multi-tenant via RLS.
            cur.execute("SET LOCAL app.current_clinic_id = %s;", (clinic_id,))
            for i, chunk in enumerate(chunks):
                embedding = gerar_embedding(chunk)
                vec = _vector_literal(embedding)
                metadata = {"chunk_index": i}
                cur.execute(
                    insert_sql,
                    (clinic_id, chunk, vec, json.dumps(metadata)),
                )
                inserted += 1
        conn.commit()

    return inserted

