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
