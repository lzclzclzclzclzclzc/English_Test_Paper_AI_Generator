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


def test_user_detail_includes_credits(client):
    boss = _mk(client, "boss", admin=True)
    victim = _mk(client, "victim")
    _as(client, boss)
    r = client.get(f"/api/admin/users/{victim.id}")
    assert r.status_code == 200
    body = r.json()
    # 账户惰性创建：首次读取就带注册赠送 + 今日赠送（老用户也补发一次）
    assert body["credits_balance"] == 300
    assert body["credits_daily_balance"] == 30


# ---- credits / orders admin ----


def test_credits_list_and_adjust(client):
    boss = _mk(client, "boss", admin=True)
    alice = _mk(client, "alice")
    _as(client, boss)

    r = client.get("/api/admin/credits?q=ali")
    assert r.status_code == 200
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["username"] == "alice"
    assert r.json()["items"][0]["balance"] == 0

    r = client.post(f"/api/admin/credits/{alice.id}/adjust", json={"delta": 500, "note": "补偿"})
    assert r.status_code == 200
    assert r.json()["balance"] == 300 + 500  # 首次触达自动带注册赠送 300

    r = client.post("/api/admin/credits/adjust", json={"username": "alice", "delta": -200, "note": "收回"})
    assert r.status_code == 200
    assert r.json()["balance"] == 600

    # 不会减到负数
    r = client.post(f"/api/admin/credits/{alice.id}/adjust", json={"delta": -9999, "note": "清零"})
    assert r.status_code == 200
    assert r.json()["balance"] == 0

    # delta=0 拒绝；未知用户 404；空备注 422
    assert client.post(f"/api/admin/credits/{alice.id}/adjust", json={"delta": 0, "note": "x"}).status_code == 400
    assert client.post("/api/admin/credits/adjust", json={"username": "nobody", "delta": 1, "note": "x"}).status_code == 404
    assert client.post(f"/api/admin/credits/{alice.id}/adjust", json={"delta": 1, "note": ""}).status_code == 422

    detail = client.get(f"/api/admin/credits/{alice.id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["username"] == "alice"
    assert body["ledger_total"] >= 3
    kinds = {row["kind"] for row in body["ledger"]}
    assert "admin_adjust" in kinds
    audit = storage.list_admin_audit(action="adjust_credits")[0]
    assert len(audit) == 3


def test_orders_list_attaches_usernames(client):
    from backend.services.payment import orders as order_service

    boss = _mk(client, "boss", admin=True)
    alice = _mk(client, "alice")
    _as(client, boss)
    order = order_service.create_order(alice.id, "starter", "qr")
    order_service.mark_order_paid(order["out_trade_no"], "MOCK")

    r = client.get("/api/admin/orders")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    item = data["items"][0]
    assert item["username"] == "alice"
    assert item["pack_id"] == "starter"
    assert item["credits"] == 1000
    assert item["status"] == "PAID"

    rev = client.get("/api/admin/stats/revenue?days=30")
    assert rev.status_code == 200
    assert rev.json()["total_cents"] == 990
    assert rev.json()["by_pack"][0]["pack_id"] == "starter"

    ov = client.get("/api/admin/stats/overview")
    assert ov.json()["paying_users"] == 1
    assert ov.json()["total_revenue_cents"] == 990


def test_credits_endpoints_require_admin(client):
    normie = _mk(client, "normie3")
    _as(client, normie)
    assert client.get("/api/admin/credits").status_code == 403
    assert client.get("/api/admin/orders").status_code == 403
    assert client.post(f"/api/admin/credits/{normie.id}/adjust", json={"delta": 1, "note": "x"}).status_code == 403


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
