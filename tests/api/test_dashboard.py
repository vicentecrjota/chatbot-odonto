"""Testes dos endpoints de dashboard."""

from unittest.mock import MagicMock, patch

from tests.conftest import AUTH_HEADERS, make_sb_mock

CLINIC_ID = "1bc4c3d2-9a23-4d58-895e-531156f8883b"
CONV_ID = "be736ec2-1cd0-47b7-a508-9267c0de51ee"

CONV_DATA = {
    "id": CONV_ID,
    "patient_phone": "554896797588",
    "status": "active",
    "created_at": "2026-03-30T19:19:33+00:00",
    "expires_at": None,
}


def test_listar_conversas(client):
    # Primeira chamada: lista; segunda: count
    sb = MagicMock()
    chain = MagicMock()
    result_list = MagicMock()
    result_list.data = [CONV_DATA]
    result_count = MagicMock()
    result_count.data = [CONV_DATA]
    result_count.count = 1

    chain.execute.side_effect = [result_list, result_count]
    for m in ("select", "eq", "order", "range", "neq", "lt", "lte", "gte", "limit"):
        getattr(chain, m).return_value = chain
    sb.table.return_value = chain

    with patch("app.api.dashboard.get_supabase_client", return_value=sb):
        resp = client.get(f"/admin/dashboard/{CLINIC_ID}/conversations", headers=AUTH_HEADERS)

    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data
    assert "total" in data


def test_listar_conversas_sem_auth(client):
    resp = client.get(f"/admin/dashboard/{CLINIC_ID}/conversations")
    assert resp.status_code == 422


def test_detalhe_conversa(client):
    full_conv = {**CONV_DATA, "messages": [{"role": "user", "content": "Oi"}], "clinic_id": CLINIC_ID}
    sb, _, _ = make_sb_mock(data=[full_conv])
    with patch("app.api.dashboard.get_supabase_client", return_value=sb):
        resp = client.get(
            f"/admin/dashboard/{CLINIC_ID}/conversations/{CONV_ID}",
            headers=AUTH_HEADERS,
        )
    assert resp.status_code == 200
    assert "messages" in resp.json()


def test_detalhe_conversa_nao_encontrada(client):
    sb, _, _ = make_sb_mock(data=[])
    with patch("app.api.dashboard.get_supabase_client", return_value=sb):
        resp = client.get(
            f"/admin/dashboard/{CLINIC_ID}/conversations/{CONV_ID}",
            headers=AUTH_HEADERS,
        )
    assert resp.status_code == 404


def test_fila_handoff_vazia(client):
    sb, _, _ = make_sb_mock(data=[])
    with patch("app.api.dashboard.get_supabase_client", return_value=sb):
        resp = client.get(f"/admin/dashboard/{CLINIC_ID}/handoff", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    assert resp.json() == []


def test_fila_handoff_com_itens(client):
    handoff_conv = {**CONV_DATA, "status": "human_takeover"}
    sb, _, _ = make_sb_mock(data=[handoff_conv])
    with patch("app.api.dashboard.get_supabase_client", return_value=sb):
        resp = client.get(f"/admin/dashboard/{CLINIC_ID}/handoff", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_resolver_handoff(client):
    resolved = {**CONV_DATA, "status": "active"}
    sb, _, _ = make_sb_mock(data=[resolved])
    with patch("app.api.dashboard.get_supabase_client", return_value=sb):
        resp = client.patch(
            f"/admin/dashboard/{CLINIC_ID}/handoff/{CONV_ID}/resolve",
            headers=AUTH_HEADERS,
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


def test_fechar_conversa(client):
    closed = {**CONV_DATA, "status": "closed"}
    sb, _, _ = make_sb_mock(data=[closed])
    with patch("app.api.dashboard.get_supabase_client", return_value=sb):
        resp = client.patch(
            f"/admin/dashboard/{CLINIC_ID}/handoff/{CONV_ID}/close",
            headers=AUTH_HEADERS,
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "closed"


def test_analytics(client):
    sb = MagicMock()
    chain = MagicMock()

    conv_result = MagicMock()
    conv_result.data = [{"status": "active"}, {"status": "active"}, {"status": "human_takeover"}]

    pac_result = MagicMock()
    pac_result.data = []
    pac_result.count = 5

    consent_result = MagicMock()
    consent_result.data = []
    consent_result.count = 4

    appt_result = MagicMock()
    appt_result.data = [
        {"status": "scheduled", "reminder_sent": False},
        {"status": "scheduled", "reminder_sent": True},
    ]

    chain.execute.side_effect = [conv_result, pac_result, consent_result, appt_result]
    for m in ("select", "eq", "order", "range", "neq", "lt", "lte", "gte", "limit"):
        getattr(chain, m).return_value = chain
    sb.table.return_value = chain

    with patch("app.api.dashboard.get_supabase_client", return_value=sb):
        resp = client.get(f"/admin/dashboard/{CLINIC_ID}/analytics", headers=AUTH_HEADERS)

    assert resp.status_code == 200
    data = resp.json()
    assert "conversas" in data
    assert "pacientes" in data
    assert "consultas" in data
    assert data["conversas"]["total"] == 3
    assert data["pacientes"]["total"] == 5
    assert data["consultas"]["lembretes_enviados"] == 1
