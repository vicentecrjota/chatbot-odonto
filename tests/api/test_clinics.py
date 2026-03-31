"""Testes dos endpoints CRUD de clínicas."""

from unittest.mock import patch

from tests.conftest import AUTH_HEADERS, make_sb_mock

CLINIC_ID = "1bc4c3d2-9a23-4d58-895e-531156f8883b"

CLINIC_DATA = {
    "id": CLINIC_ID,
    "name": "Clínica Teste",
    "whatsapp_number": "+5548999999999",
    "whatsapp_phone_number_id": "123456",
    "plan_type": "basic",
    "rag_config": {},
    "active": True,
    "created_at": "2026-01-01T00:00:00+00:00",
}


def test_listar_clinicas(client):
    sb, _, _ = make_sb_mock(data=[CLINIC_DATA])
    with patch("app.api.clinics.get_supabase_client", return_value=sb):
        resp = client.get("/admin/clinics", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert resp.json()[0]["name"] == "Clínica Teste"


def test_listar_clinicas_sem_auth(client):
    resp = client.get("/admin/clinics")
    assert resp.status_code == 422


def test_listar_clinicas_api_key_invalida(client):
    resp = client.get("/admin/clinics", headers={"X-API-Key": "errada"})
    assert resp.status_code == 401


def test_buscar_clinica(client):
    sb, _, _ = make_sb_mock(data=[CLINIC_DATA])
    with patch("app.api.clinics.get_supabase_client", return_value=sb):
        resp = client.get(f"/admin/clinics/{CLINIC_ID}", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["id"] == CLINIC_ID


def test_buscar_clinica_nao_encontrada(client):
    sb, _, _ = make_sb_mock(data=[])
    with patch("app.api.clinics.get_supabase_client", return_value=sb):
        resp = client.get(f"/admin/clinics/{CLINIC_ID}", headers=AUTH_HEADERS)
    assert resp.status_code == 404


def test_criar_clinica(client):
    sb, _, _ = make_sb_mock(data=[CLINIC_DATA])
    payload = {
        "name": "Clínica Teste",
        "whatsapp_number": "+5548999999999",
    }
    with patch("app.api.clinics.get_supabase_client", return_value=sb):
        resp = client.post("/admin/clinics", headers=AUTH_HEADERS, json=payload)
    assert resp.status_code == 201
    assert resp.json()["name"] == "Clínica Teste"


def test_atualizar_clinica(client):
    updated = {**CLINIC_DATA, "name": "Clínica Atualizada"}
    sb, _, _ = make_sb_mock(data=[updated])
    with patch("app.api.clinics.get_supabase_client", return_value=sb):
        resp = client.put(
            f"/admin/clinics/{CLINIC_ID}",
            headers=AUTH_HEADERS,
            json={"name": "Clínica Atualizada"},
        )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Clínica Atualizada"


def test_atualizar_clinica_sem_campos(client):
    sb, _, _ = make_sb_mock(data=[])
    with patch("app.api.clinics.get_supabase_client", return_value=sb):
        resp = client.put(
            f"/admin/clinics/{CLINIC_ID}",
            headers=AUTH_HEADERS,
            json={},
        )
    assert resp.status_code == 400


def test_deletar_clinica(client):
    sb, _, _ = make_sb_mock(data=[])
    with patch("app.api.clinics.get_supabase_client", return_value=sb):
        resp = client.delete(f"/admin/clinics/{CLINIC_ID}", headers=AUTH_HEADERS)
    assert resp.status_code == 204
