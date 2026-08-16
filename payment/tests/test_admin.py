from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def make_client(tmp_path, monkeypatch):
    """Build a payment app TestClient authenticated as a dev-fake user with a given role."""
    def _build(role: str) -> TestClient:
        monkeypatch.setenv("MOCK_PAY", "true")
        monkeypatch.setenv("DB_PATH", str(tmp_path / "pay.db"))
        monkeypatch.setenv("PAYMENT_DEV_FAKE_USER", "tester")
        monkeypatch.setenv("PAYMENT_DEV_FAKE_ROLE", role)
        from app.config import get_settings
        get_settings.cache_clear()
        import app.alipay_client as alipay_client
        alipay_client._client = None
        from app.db import init_db
        init_db()
        from app.main import create_app
        return TestClient(create_app())
    return _build


def test_admin_memberships_forbidden_for_user(make_client):
    c = make_client("user")
    assert c.get("/payapi/admin/memberships").status_code == 403


def test_admin_memberships_ok_for_admin(make_client):
    c = make_client("admin")
    r = c.get("/payapi/admin/memberships")
    assert r.status_code == 200
    assert r.json() == {"items": [], "total": 0}


from app import service
from app.config import parse_iso, utcnow


def test_extend_membership_from_scratch(make_client):
    # build_client also sets DB_PATH + init_db for this tmp db
    make_client("admin")
    exp = service.extend_membership("newbie", 30)
    assert parse_iso(exp) > utcnow()


def test_grant_and_revoke_via_api(make_client):
    c = make_client("admin")
    r = c.post("/payapi/admin/memberships/u42/grant", json={"days": 30})
    assert r.status_code == 200
    assert r.json()["active"] is True
    r2 = c.post("/payapi/admin/memberships/u42/revoke")
    assert r2.status_code == 200
    assert r2.json()["active"] is False


def test_orders_list_admin_only(make_client):
    assert make_client("user").get("/payapi/admin/orders").status_code == 403
    assert make_client("admin").get("/payapi/admin/orders").status_code == 200


def test_membership_list_reflects_grant(make_client):
    c = make_client("admin")
    c.post("/payapi/admin/memberships/u99/grant", json={"days": 10})
    data = c.get("/payapi/admin/memberships?q=u99").json()
    assert data["total"] == 1
    assert data["items"][0]["user_id"] == "u99"
    assert data["items"][0]["active"] is True


def test_grant_requires_days_or_plan(make_client):
    c = make_client("admin")
    r = c.post("/payapi/admin/memberships/u1/grant", json={})
    assert r.status_code == 422


# ---- Spec H D1/D2: revenue stats, expiring filter, health ----


def _insert_order(out_trade_no, status, cents, paid_at=None, plan_id="monthly"):
    from app.config import format_iso, utcnow
    from app.db import get_conn

    now = format_iso(utcnow())
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO orders(out_trade_no, user_id, plan_id, amount_cents, status,"
            " created_at, expires_at, paid_at) VALUES(?,?,?,?,?,?,?,?)",
            (out_trade_no, "u1", plan_id, cents, status, now, now, paid_at),
        )


def test_revenue_stats_counts_paid_only(make_client):
    from app.config import format_iso, utcnow

    make_client("admin")  # init tmp db
    today = format_iso(utcnow())
    _insert_order("T1", "PAID", 100, paid_at=today)
    _insert_order("T2", "CREATED", 999)  # unpaid never counts
    _insert_order("T3", "PAID", 500, paid_at=format_iso(utcnow() - __import__("datetime").timedelta(days=40)))

    stats = service.revenue_stats(30)
    assert stats["total_cents"] == 600  # all-history, PAID only
    assert sum(d["cents"] for d in stats["revenue_by_day"]) == 100  # windowed
    assert stats["by_plan"] == [{"plan_id": "monthly", "orders": 1, "cents": 100}]


def test_revenue_endpoint_admin_only(make_client):
    assert make_client("user").get("/payapi/admin/stats/revenue").status_code == 403
    assert make_client("admin").get("/payapi/admin/stats/revenue").status_code == 200


def test_memberships_expiring_within_days_boundary(make_client):
    from datetime import timedelta

    from app.config import format_iso, utcnow
    from app.db import get_conn

    make_client("admin")
    service.extend_membership("soon", 5)  # expires in 5 days → within 7
    service.extend_membership("edge", 7)  # exactly 7 days → inclusive
    service.extend_membership("far", 30)  # outside the window
    service.revoke_membership("gone")  # already expired → never matches
    with get_conn() as conn:
        conn.execute(
            "UPDATE memberships SET expires_at=? WHERE user_id='gone'",
            (format_iso(utcnow() - timedelta(days=1)),),
        )

    items = service.list_memberships(expiring_within_days=7)
    users = {i["user_id"] for i in items}
    assert "soon" in users
    assert "edge" in users
    assert "far" not in users
    assert "gone" not in users


def test_memberships_expiring_param_via_api(make_client):
    c = make_client("admin")
    service.extend_membership("u_soon", 3)
    r = c.get("/payapi/admin/memberships?expiring_within_days=7")
    assert r.status_code == 200
    users = {i["user_id"] for i in r.json()["items"]}
    assert "u_soon" in users


def test_health_endpoint(make_client):
    c = make_client("admin")
    r = c.get("/payapi/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
