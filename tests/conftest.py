"""Configuração global dos testes — env vars e fixtures compartilhadas."""

import os

# Setar variáveis ANTES de qualquer import de módulos da app.
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("META_ACCESS_TOKEN", "test-meta-token")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")

from unittest.mock import MagicMock  # noqa: E402

import pytest  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402

# Limpa o cache do lru_cache para garantir que os valores acima sejam usados.
get_settings.cache_clear()


TEST_API_KEY = "test-api-key"
AUTH_HEADERS = {"X-API-Key": TEST_API_KEY}


def make_sb_mock(data=None, count=None):
    """
    Cria um mock do cliente Supabase com encadeamento de métodos.
    Todos os métodos de query retornam o próprio mock (fluent interface).
    """
    result = MagicMock()
    result.data = data if data is not None else []
    result.count = count

    chain = MagicMock()
    chain.execute.return_value = result

    for method in (
        "select", "insert", "update", "delete",
        "eq", "neq", "lt", "lte", "gte",
        "limit", "order", "range",
    ):
        getattr(chain, method).return_value = chain

    sb = MagicMock()
    sb.table.return_value = chain
    return sb, chain, result


@pytest.fixture()
def client():
    """TestClient do FastAPI com lifespan desativado (sem APScheduler nos testes)."""
    from app.main import create_app
    application = create_app()
    with TestClient(application, raise_server_exceptions=True) as c:
        yield c
