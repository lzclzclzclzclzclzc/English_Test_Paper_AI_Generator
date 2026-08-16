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


def test_banned_user_cannot_login(client):
    from shared import storage

    assert client.post("/api/auth/register", json={"username": "mallory", "password": "demo123"}).status_code == 200
    user = storage.get_user_by_username("mallory")
    storage.set_user_status(user.id, "banned")

    # 正确密码也拒绝登录（403 auth.forbidden），且不种会话
    r = client.post("/api/auth/login", json={"username": "mallory", "password": "demo123"})
    assert r.status_code == 403
    assert r.json()["error_code"] == "auth.forbidden"
    assert "session_id" not in r.cookies

    # 封禁前残留的会话也被吊销
    assert client.get("/api/auth/me").status_code == 401

    # 解封后可正常登录
    storage.set_user_status(user.id, "active")
    ok = client.post("/api/auth/login", json={"username": "mallory", "password": "demo123"})
    assert ok.status_code == 200
    assert client.get("/api/auth/me").status_code == 200
