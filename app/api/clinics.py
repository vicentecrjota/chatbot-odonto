"""Endpoints administrativos para gerenciamento de clínicas."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel

from app.core.auth import require_api_key
from app.database import get_supabase_client
from app.services.rag_service import RagServiceError, indexar_documento

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/clinics", tags=["Admin — Clinics"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ClinicCreate(BaseModel):
    name: str
    whatsapp_number: str
    whatsapp_phone_number_id: str | None = None
    instagram_page_id: str | None = None
    reception_phone: str | None = None
    google_calendar_id: str | None = None
    plan_type: str = "basic"
    rag_config: dict[str, Any] = {}
    active: bool = True


class ClinicUpdate(BaseModel):
    name: str | None = None
    whatsapp_number: str | None = None
    whatsapp_phone_number_id: str | None = None
    instagram_page_id: str | None = None
    reception_phone: str | None = None
    google_calendar_id: str | None = None
    plan_type: str | None = None
    rag_config: dict[str, Any] | None = None
    active: bool | None = None


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.get("", dependencies=[Depends(require_api_key)])
def listar_clinicas() -> list[dict]:
    """Lista todas as clínicas cadastradas."""
    sb = get_supabase_client()
    resp = sb.table("clinics").select("*").order("created_at", desc=True).execute()
    return getattr(resp, "data", []) or []


@router.get("/{clinic_id}", dependencies=[Depends(require_api_key)])
def buscar_clinica(clinic_id: str) -> dict:
    """Retorna dados de uma clínica pelo ID."""
    sb = get_supabase_client()
    resp = sb.table("clinics").select("*").eq("id", clinic_id).limit(1).execute()
    data = getattr(resp, "data", None)
    if not data:
        raise HTTPException(status_code=404, detail="Clínica não encontrada.")
    return data[0]


@router.post("", dependencies=[Depends(require_api_key)], status_code=201)
def criar_clinica(payload: ClinicCreate) -> dict:
    """Cadastra uma nova clínica."""
    sb = get_supabase_client()
    resp = sb.table("clinics").insert(payload.model_dump()).execute()
    data = getattr(resp, "data", None)
    if not data:
        raise HTTPException(status_code=500, detail="Erro ao criar clínica.")
    return data[0]


@router.put("/{clinic_id}", dependencies=[Depends(require_api_key)])
def atualizar_clinica(clinic_id: str, payload: ClinicUpdate) -> dict:
    """Atualiza dados de uma clínica."""
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="Nenhum campo para atualizar.")
    sb = get_supabase_client()
    resp = sb.table("clinics").update(updates).eq("id", clinic_id).execute()
    data = getattr(resp, "data", None)
    if not data:
        raise HTTPException(status_code=404, detail="Clínica não encontrada.")
    return data[0]


@router.delete("/{clinic_id}", dependencies=[Depends(require_api_key)], status_code=204)
def deletar_clinica(clinic_id: str) -> None:
    """Remove uma clínica e todos os dados associados (cascade)."""
    sb = get_supabase_client()
    sb.table("clinics").delete().eq("id", clinic_id).execute()


# ---------------------------------------------------------------------------
# Documentos RAG
# ---------------------------------------------------------------------------

@router.post("/{clinic_id}/documents", dependencies=[Depends(require_api_key)])
async def upload_documento(
    clinic_id: str,
    file: UploadFile = File(...),
) -> dict:
    """
    Recebe um arquivo de texto (.txt) ou PDF simples,
    indexa no RAG e retorna o número de chunks gerados.
    """
    content_type = file.content_type or ""
    if "text" not in content_type and "pdf" not in content_type:
        raise HTTPException(
            status_code=400,
            detail="Apenas arquivos .txt ou .pdf são aceitos.",
        )

    raw = await file.read()

    if "pdf" in content_type:
        try:
            import io
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(raw))
            texto = "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Erro ao ler PDF: {e}")
    else:
        texto = raw.decode("utf-8", errors="ignore")

    if not texto.strip():
        raise HTTPException(status_code=400, detail="Arquivo vazio ou sem texto extraível.")

    try:
        chunks = indexar_documento(clinic_id, texto)
    except RagServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"clinic_id": clinic_id, "filename": file.filename, "chunks_indexed": chunks}


@router.get("/{clinic_id}/documents", dependencies=[Depends(require_api_key)])
def listar_documentos(clinic_id: str) -> list[dict]:
    """Lista todos os documentos RAG de uma clínica (sem o campo embedding)."""
    sb = get_supabase_client()
    resp = (
        sb.table("rag_documents")
        .select("id, content, metadata")
        .eq("clinic_id", clinic_id)
        .order("id")
        .execute()
    )
    return getattr(resp, "data", []) or []


@router.delete("/{clinic_id}/documents/{document_id}", dependencies=[Depends(require_api_key)], status_code=204)
def deletar_documento(clinic_id: str, document_id: str) -> None:
    """Remove um documento RAG específico."""
    sb = get_supabase_client()
    sb.table("rag_documents").delete().eq("clinic_id", clinic_id).eq("id", document_id).execute()


@router.delete("/{clinic_id}/documents", dependencies=[Depends(require_api_key)], status_code=204)
def deletar_documentos(clinic_id: str) -> None:
    """Remove todos os documentos RAG de uma clínica."""
    sb = get_supabase_client()
    sb.table("rag_documents").delete().eq("clinic_id", clinic_id).execute()
