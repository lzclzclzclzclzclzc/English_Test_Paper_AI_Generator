from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.auth.password import hash_password
from shared import storage


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("BACKEND_ENV", "test")
    from shared.config import reset_config_cache
    reset_config_cache()
    storage.set_db_path(tmp_path / "api.db")
    storage.init_db()
    app = create_app()
    with TestClient(app) as c:
        yield c
    storage.set_db_path(None)
    reset_config_cache()


def _mk(client, username, admin=False):
    storage.create_user(username, hash_password("secret1"))
    u = storage.get_user_by_username(username)
    if admin:
        storage.set_user_role(u.id, "admin")
    return u


def _as(client, u):
    sid = storage.create_session(u.id)
    client.cookies.set("session_id", sid)


def test_users_list_requires_admin(client):
    normie = _mk(client, "normie")
    _as(client, normie)
    assert client.get("/api/admin/users").status_code == 403


def test_users_list_ok_for_admin(client):
    boss = _mk(client, "boss", admin=True)
    _mk(client, "u1")
    _as(client, boss)
    r = client.get("/api/admin/users?q=u1")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["username"] == "u1"


def test_set_role_cannot_change_self(client):
    boss = _mk(client, "boss", admin=True)
    _as(client, boss)
    r = client.post(f"/api/admin/users/{boss.id}/role", json={"role": "user"})
    assert r.status_code == 400


def test_reset_password_and_wipe_sessions(client):
    boss = _mk(client, "boss", admin=True)
    victim = _mk(client, "victim")
    victim_sid = storage.create_session(victim.id)
    _as(client, boss)
    r = client.post(f"/api/admin/users/{victim.id}/reset-password", json={"new_password": "brandnew1"})
    assert r.status_code == 200
    assert storage.get_session(victim_sid) is None


def test_ban_and_unban(client):
    boss = _mk(client, "boss", admin=True)
    victim = _mk(client, "victim")
    victim_sid = storage.create_session(victim.id)
    _as(client, boss)
    assert client.post(f"/api/admin/users/{victim.id}/ban").status_code == 200
    assert storage.get_session(victim_sid) is None
    assert storage.get_user_by_id(victim.id).status == "banned"
    assert client.post(f"/api/admin/users/{victim.id}/unban").status_code == 200
    assert storage.get_user_by_id(victim.id).status == "active"


def test_cannot_ban_self(client):
    boss = _mk(client, "boss", admin=True)
    _as(client, boss)
    assert client.post(f"/api/admin/users/{boss.id}/ban").status_code == 400
