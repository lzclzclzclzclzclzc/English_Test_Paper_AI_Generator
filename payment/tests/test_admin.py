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
