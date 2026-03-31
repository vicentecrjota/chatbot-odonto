"""Testes unitários do serviço RAG (chunking e formatação de vetor)."""

from app.services.rag_service import _chunk_text_by_tokens, _vector_literal


def test_chunk_texto_vazio():
    assert _chunk_text_by_tokens("") == []


def test_chunk_texto_curto():
    chunks = _chunk_text_by_tokens("Olá, mundo!", tokens_por_chunk=400)
    assert len(chunks) == 1
    assert "Olá" in chunks[0]


def test_chunk_divide_texto_longo():
    # Gera texto longo o suficiente para criar múltiplos chunks de 10 tokens
    palavra = "odontologia "
    texto = palavra * 50  # ~100 tokens
    chunks = _chunk_text_by_tokens(texto, tokens_por_chunk=10)
    assert len(chunks) > 1


def test_chunk_preserva_conteudo():
    texto = "Clínica odontológica especializada em implantes e ortodontia."
    chunks = _chunk_text_by_tokens(texto, tokens_por_chunk=400)
    reconstruido = "".join(chunks)
    # Conteúdo essencial deve estar presente
    assert "implantes" in reconstruido
    assert "ortodontia" in reconstruido


def test_vector_literal_formato():
    embedding = [0.1, 0.2, 0.3]
    result = _vector_literal(embedding)
    assert result.startswith("[")
    assert result.endswith("]")
    assert "," in result


def test_vector_literal_dimensao_correta():
    embedding = [0.0] * 1536
    result = _vector_literal(embedding)
    valores = result.strip("[]").split(",")
    assert len(valores) == 1536


def test_vector_literal_precisao():
    embedding = [0.123456789012]
    result = _vector_literal(embedding)
    # Deve ter 10 casas decimais
    assert "0.1234567890" in result
