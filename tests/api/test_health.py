"""Testes do endpoint /health."""


def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert "version" in data


def test_health_sem_autenticacao(client):
    """Health não requer API Key."""
    resp = client.get("/health")
    assert resp.status_code == 200
