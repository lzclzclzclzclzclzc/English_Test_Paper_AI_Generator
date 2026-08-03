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
    # A stale session created before unban must also be cleared — unban forces
    # re-authentication, symmetric with ban / reset-password.
    stale_sid = storage.create_session(victim.id)
    assert client.post(f"/api/admin/users/{victim.id}/unban").status_code == 200
    assert storage.get_user_by_id(victim.id).status == "active"
    assert storage.get_session(stale_sid) is None


def test_cannot_ban_self(client):
    boss = _mk(client, "boss", admin=True)
    _as(client, boss)
    assert client.post(f"/api/admin/users/{boss.id}/ban").status_code == 400


def test_stats_overview_and_timeseries(client):
    boss = _mk(client, "boss", admin=True)
    _mk(client, "u1")
    _as(client, boss)
    ov = client.get("/api/admin/stats/overview")
    assert ov.status_code == 200
    assert ov.json()["total_users"] == 2
    ts = client.get("/api/admin/stats/timeseries?days=7")
    assert ts.status_code == 200
    body = ts.json()
    assert "users_by_day" in body and "papers_by_day" in body


def test_stats_requires_admin(client):
    normie = _mk(client, "normie2")
    _as(client, normie)
    assert client.get("/api/admin/stats/overview").status_code == 403


def test_user_detail_includes_membership_when_payment_ok(client, monkeypatch):
    boss = _mk(client, "boss", admin=True)
    victim = _mk(client, "victim")
    _as(client, boss)

    import backend.api.admin as admin_mod

    def fake_fetch(user_id, cookie):
        return "2099-01-01T00:00:00Z"

    monkeypatch.setattr(admin_mod, "_fetch_membership_expiry", fake_fetch)
    r = client.get(f"/api/admin/users/{victim.id}")
    assert r.status_code == 200
    assert r.json()["membership_expires_at"] == "2099-01-01T00:00:00Z"


# ---- membership/order aggregation (username enrichment) ----


def test_memberships_list_attaches_usernames(client, monkeypatch):
    boss = _mk(client, "boss", admin=True)
    alice = _mk(client, "alice")
    _as(client, boss)

    import backend.api.admin as admin_mod

    def fake_get(path, cookie, params=None):
        return {
            "items": [
                {"user_id": alice.id, "expires_at": "2099-01-01T00:00:00Z", "active": True},
                {"user_id": "ghost", "expires_at": None, "active": False},
            ],
            "total": 2,
        }

    monkeypatch.setattr(admin_mod, "_payment_get_json", fake_get)
    r = client.get("/api/admin/memberships")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2
    by_id = {m["user_id"]: m for m in data["items"]}
    assert by_id[alice.id]["username"] == "alice"
    assert by_id["ghost"]["username"] is None


def test_memberships_list_filters_by_username(client, monkeypatch):
    boss = _mk(client, "boss", admin=True)
    alice = _mk(client, "alice")
    bob = _mk(client, "bob")
    _as(client, boss)

    import backend.api.admin as admin_mod

    def fake_get(path, cookie, params=None):
        return {
            "items": [
                {"user_id": alice.id, "expires_at": None, "active": True},
                {"user_id": bob.id, "expires_at": None, "active": True},
                {"user_id": "ghost", "expires_at": None, "active": False},
            ],
            "total": 3,
        }

    monkeypatch.setattr(admin_mod, "_payment_get_json", fake_get)
    r = client.get("/api/admin/memberships?q=alic")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["username"] == "alice"


def test_memberships_list_upstream_error_is_502(client, monkeypatch):
    boss = _mk(client, "boss", admin=True)
    _as(client, boss)

    import backend.api.admin as admin_mod
    from backend.errors import PaymentUpstreamError

    def fake_get(path, cookie, params=None):
        raise PaymentUpstreamError("boom")

    monkeypatch.setattr(admin_mod, "_payment_get_json", fake_get)
    r = client.get("/api/admin/memberships")
    assert r.status_code == 502


def test_orders_list_attaches_usernames(client, monkeypatch):
    boss = _mk(client, "boss", admin=True)
    alice = _mk(client, "alice")
    _as(client, boss)

    import backend.api.admin as admin_mod

    def fake_get(path, cookie, params=None):
        return {
            "items": [
                {
                    "out_trade_no": "T1",
                    "user_id": alice.id,
                    "plan_id": "monthly",
                    "amount_cents": 990,
                    "status": "paid",
                    "created_at": "2026-01-01T00:00:00Z",
                    "paid_at": "2026-01-01T00:05:00Z",
                    # extras that must be ignored by the schema
                    "channel": "alipay",
                    "qr_code": "xxx",
                },
                {
                    "out_trade_no": "T2",
                    "user_id": "ghost",
                    "plan_id": "yearly",
                    "amount_cents": 9900,
                    "status": "pending",
                    "created_at": "2026-01-02T00:00:00Z",
                },
            ]
        }

    monkeypatch.setattr(admin_mod, "_payment_get_json", fake_get)
    r = client.get("/api/admin/orders")
    assert r.status_code == 200
    items = r.json()["items"]
    by_no = {o["out_trade_no"]: o for o in items}
    assert by_no["T1"]["username"] == "alice"
    assert by_no["T1"]["paid_at"] == "2026-01-01T00:05:00Z"
    assert by_no["T2"]["username"] is None
    assert by_no["T2"]["paid_at"] is None


def test_grant_by_username_known_user(client, monkeypatch):
    boss = _mk(client, "boss", admin=True)
    alice = _mk(client, "alice")
    _as(client, boss)

    import backend.api.admin as admin_mod

    captured = {}

    def fake_post(path, cookie, json=None):
        captured["path"] = path
        captured["json"] = json
        return {"user_id": alice.id, "expires_at": "2099-01-01T00:00:00Z", "active": True}

    monkeypatch.setattr(admin_mod, "_payment_post_json", fake_post)
    r = client.post("/api/admin/memberships/grant", json={"username": "alice", "days": 30})
    assert r.status_code == 200
    assert r.json()["user_id"] == alice.id
    assert captured["path"] == f"/payapi/admin/memberships/{alice.id}/grant"
    assert captured["json"] == {"days": 30}


def test_grant_by_username_unknown_user_404(client, monkeypatch):
    boss = _mk(client, "boss", admin=True)
    _as(client, boss)

    import backend.api.admin as admin_mod

    def fake_post(path, cookie, json=None):
        raise AssertionError("payment must not be called for unknown user")

    monkeypatch.setattr(admin_mod, "_payment_post_json", fake_post)
    r = client.post("/api/admin/memberships/grant", json={"username": "nobody", "days": 30})
    assert r.status_code == 404


def test_grant_by_user_id_forwarder(client, monkeypatch):
    boss = _mk(client, "boss", admin=True)
    alice = _mk(client, "alice")
    _as(client, boss)

    import backend.api.admin as admin_mod

    def fake_post(path, cookie, json=None):
        assert path == f"/payapi/admin/memberships/{alice.id}/grant"
        assert json == {"days": 7}
        return {"user_id": alice.id, "active": True}

    monkeypatch.setattr(admin_mod, "_payment_post_json", fake_post)
    r = client.post(f"/api/admin/memberships/{alice.id}/grant", json={"days": 7})
    assert r.status_code == 200


def test_revoke_forwarder(client, monkeypatch):
    boss = _mk(client, "boss", admin=True)
    alice = _mk(client, "alice")
    _as(client, boss)

    import backend.api.admin as admin_mod

    def fake_post(path, cookie, json=None):
        assert path == f"/payapi/admin/memberships/{alice.id}/revoke"
        return {"user_id": alice.id, "active": False}

    monkeypatch.setattr(admin_mod, "_payment_post_json", fake_post)
    r = client.post(f"/api/admin/memberships/{alice.id}/revoke")
    assert r.status_code == 200
    assert r.json()["active"] is False


def test_memberships_endpoints_require_admin(client, monkeypatch):
    normie = _mk(client, "normie3")
    _as(client, normie)
    assert client.get("/api/admin/memberships").status_code == 403
    assert client.get("/api/admin/orders").status_code == 403
    assert client.post("/api/admin/memberships/grant", json={"username": "x", "days": 1}).status_code == 403


# ---- analytics / user mastery ----


def _seed_attempt(user_id, kp="kp_a", qt="single_choice", correct=True):
    from datetime import datetime, timezone
    from backend.schemas import StoredAttempt, StoredAttemptItem

    storage.write_attempt(
        StoredAttempt(
            user_id=user_id,
            paper_id="p_" + user_id,
            answered_at=datetime.now(timezone.utc),
            items=[
                StoredAttemptItem(
                    index=1,
                    source_question_id="q_00001",
                    knowledge_point_ids=[kp],
                    question_type=qt,
                    is_correct=correct,
                )
            ],
        )
    )


def test_analytics_requires_admin(client):
    normie = _mk(client, "normie4")
    _as(client, normie)
    assert client.get("/api/admin/analytics").status_code == 403


def test_analytics_ok_for_admin(client):
    boss = _mk(client, "boss", admin=True)
    u1 = _mk(client, "u1")
    _seed_attempt(u1.id, kp="kp_a", correct=False)
    _as(client, boss)
    r = client.get("/api/admin/analytics?days=30")
    assert r.status_code == 200
    body = r.json()
    assert set(body) >= {"site_mastery", "attempts_by_day", "type_accuracy"}
    assert body["site_mastery"]["user_id"] == "__all__"
    assert body["site_mastery"]["total_attempts_considered"] == 1
    assert any(t["question_type"] == "single_choice" for t in body["type_accuracy"])


def test_analytics_all_history_when_days_zero(client):
    boss = _mk(client, "boss", admin=True)
    u1 = _mk(client, "u1")
    _seed_attempt(u1.id)
    _as(client, boss)
    r = client.get("/api/admin/analytics?days=0")
    assert r.status_code == 200
    assert r.json()["site_mastery"]["window_days"] is None


def test_user_mastery_requires_admin(client):
    normie = _mk(client, "normie5")
    _as(client, normie)
    assert client.get(f"/api/admin/users/{normie.id}/mastery").status_code == 403


def test_user_mastery_404_for_missing_user(client):
    boss = _mk(client, "boss", admin=True)
    _as(client, boss)
    assert client.get("/api/admin/users/ghost/mastery").status_code == 404


def test_user_mastery_ok(client):
    boss = _mk(client, "boss", admin=True)
    u1 = _mk(client, "u1")
    _seed_attempt(u1.id, kp="kp_weak", correct=False)
    _as(client, boss)
    r = client.get(f"/api/admin/users/{u1.id}/mastery")
    assert r.status_code == 200
    body = r.json()
    assert body["user_id"] == u1.id
    assert body["total_attempts_considered"] == 1
    assert any(k["knowledge_point_id"] == "kp_weak" for k in body["weak_kps"])
