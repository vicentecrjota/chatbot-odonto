"""Testes dos endpoints LGPD."""

from unittest.mock import MagicMock, patch

from tests.conftest import AUTH_HEADERS, make_sb_mock

CLINIC_ID = "1bc4c3d2-9a23-4d58-895e-531156f8883b"
PHONE = "554896797588"

PATIENT_DATA = {
    "id": "7ffc71b7-5c8c-46fd-898f-123bcd66f6f0",
    "name": "Paciente Teste",
    "phone": PHONE,
    "consent_given": True,
    "consent_at": "2026-03-31T14:08:28+00:00",
    "metadata": {},
}

CONV_DATA = {
    "id": "be736ec2-1cd0-47b7-a508-9267c0de51ee",
    "messages": [{"role": "user", "content": "Oi"}],
    "status": "active",
    "created_at": "2026-03-30T19:19:33+00:00",
}


def _make_export_sb():
    """Mock com 3 chamadas encadeadas: paciente, conversas, consultas."""
    sb = MagicMock()
    chain = MagicMock()

    r_patient = MagicMock()
    r_patient.data = [PATIENT_DATA]

    r_convs = MagicMock()
    r_convs.data = [CONV_DATA]

    r_appts = MagicMock()
    r_appts.data = []

    chain.execute.side_effect = [r_patient, r_convs, r_appts]
    for m in ("select", "eq", "limit", "order"):
        getattr(chain, m).return_value = chain
    sb.table.return_value = chain
    return sb


def test_exportar_dados_paciente(client):
    sb = _make_export_sb()
    with patch("app.api.lgpd.get_supabase_client", return_value=sb):
        resp = client.get(
            f"/admin/lgpd/{CLINIC_ID}/patients/{PHONE}/export",
            headers=AUTH_HEADERS,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "paciente" in data
    assert "conversas" in data
    assert "consultas" in data
    assert data["paciente"]["phone"] == PHONE


def test_exportar_paciente_nao_encontrado(client):
    sb, _, _ = make_sb_mock(data=[])
    with patch("app.api.lgpd.get_supabase_client", return_value=sb):
        resp = client.get(
            f"/admin/lgpd/{CLINIC_ID}/patients/99999999/export",
            headers=AUTH_HEADERS,
        )
    assert resp.status_code == 404


def test_revogar_consentimento(client):
    updated = {**PATIENT_DATA, "consent_given": False, "consent_at": None}
    sb = MagicMock()
    chain = MagicMock()

    r_find = MagicMock()
    r_find.data = [PATIENT_DATA]

    r_update = MagicMock()
    r_update.data = [updated]

    chain.execute.side_effect = [r_find, r_update]
    for m in ("select", "update", "eq", "limit"):
        getattr(chain, m).return_value = chain
    sb.table.return_value = chain

    with patch("app.api.lgpd.get_supabase_client", return_value=sb):
        resp = client.patch(
            f"/admin/lgpd/{CLINIC_ID}/patients/{PHONE}/revoke-consent",
            headers=AUTH_HEADERS,
        )
    assert resp.status_code == 200
    assert "revogado" in resp.json()["detail"].lower()


def test_deletar_paciente(client):
    sb = MagicMock()
    chain = MagicMock()

    r_find = MagicMock()
    r_find.data = [PATIENT_DATA]

    r_del_conv = MagicMock()
    r_del_conv.data = []

    r_del_pat = MagicMock()
    r_del_pat.data = []

    chain.execute.side_effect = [r_find, r_del_conv, r_del_pat]
    for m in ("select", "delete", "eq", "neq", "limit"):
        getattr(chain, m).return_value = chain
    sb.table.return_value = chain

    with patch("app.api.lgpd.get_supabase_client", return_value=sb):
        resp = client.delete(
            f"/admin/lgpd/{CLINIC_ID}/patients/{PHONE}",
            headers=AUTH_HEADERS,
        )
    assert resp.status_code == 200
    assert "removidos permanentemente" in resp.json()["detail"]


def test_deletar_paciente_nao_encontrado(client):
    sb, _, _ = make_sb_mock(data=[])
    with patch("app.api.lgpd.get_supabase_client", return_value=sb):
        resp = client.delete(
            f"/admin/lgpd/{CLINIC_ID}/patients/99999999",
            headers=AUTH_HEADERS,
        )
    assert resp.status_code == 404


def test_endpoints_sem_auth(client):
    for method, url in [
        ("get", f"/admin/lgpd/{CLINIC_ID}/patients/{PHONE}/export"),
        ("patch", f"/admin/lgpd/{CLINIC_ID}/patients/{PHONE}/revoke-consent"),
        ("delete", f"/admin/lgpd/{CLINIC_ID}/patients/{PHONE}"),
    ]:
        resp = getattr(client, method)(url)
        assert resp.status_code == 422
