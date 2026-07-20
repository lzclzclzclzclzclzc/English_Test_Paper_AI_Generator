from __future__ import annotations


def test_register_auto_logs_in_and_me_returns_user(client):
    response = client.post("/api/auth/register", json={"username": "alice", "password": "demo123"})
    assert response.status_code == 200
    assert response.json()["username"] == "alice"
    assert "session_id" in response.cookies

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == "alice"


def test_duplicate_username_returns_stable_error(client):
    assert client.post("/api/auth/register", json={"username": "alice", "password": "demo123"}).status_code == 200
    response = client.post("/api/auth/register", json={"username": "alice", "password": "demo123"})
    assert response.status_code == 409
    assert response.json()["error_code"] == "auth.username_conflict"


def test_login_and_logout(client):
    assert client.post("/api/auth/register", json={"username": "alice", "password": "demo123"}).status_code == 200
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401

    bad = client.post("/api/auth/login", json={"username": "alice", "password": "wrong123"})
    assert bad.status_code == 401
    assert bad.json()["error_code"] == "auth.invalid_credentials"

    good = client.post("/api/auth/login", json={"username": "alice", "password": "demo123"})
    assert good.status_code == 200
    assert client.get("/api/auth/me").status_code == 200


def test_protected_route_requires_login(client):
    response = client.get("/api/papers")
    assert response.status_code == 401
    assert response.json()["error_code"] == "auth.unauthorized"
