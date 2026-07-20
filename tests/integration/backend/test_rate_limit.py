from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from backend.deps import check_rate_limit, prune_rate_limits, reset_rate_limits
from backend.errors import RateLimitError
from backend.services import ai_gateway
from shared import storage
from shared.config import get_config, reset_config_cache
from tests.integration.backend.conftest import _fake_paper


@pytest.fixture(autouse=True)
def clean_rate_limits():
    reset_rate_limits()
    yield
    reset_rate_limits()


@pytest.fixture
def limited_client(tmp_path, monkeypatch):
    reset_rate_limits()
    db_path = tmp_path / "rate-limit-test.db"
    storage.set_db_path(db_path)
    monkeypatch.setenv("SQLITE_PATH", str(db_path))
    reset_config_cache()
    monkeypatch.setenv("BACKEND_ENV", "test")
    monkeypatch.setenv("BCRYPT_ROUNDS", "4")
    monkeypatch.setenv("RATE_LIMIT_GENERATE_PER_MIN", "1")
    monkeypatch.setattr(ai_gateway, "generate_paper", _fake_paper)
    get_config()
    from backend.main import create_app

    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    storage.set_db_path(None)
    reset_rate_limits()
    reset_config_cache()


def test_generate_rate_limit_returns_429(limited_client):
    assert limited_client.post("/api/auth/register", json={"username": "demo", "password": "demo123"}).status_code == 200
    first = limited_client.post("/api/papers/generate", json={"user_query": "来 1 道选择题", "mode": "fresh"})
    second = limited_client.post("/api/papers/generate", json={"user_query": "来 1 道选择题", "mode": "fresh"})

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["error_code"] == "rate.exceeded"


def test_reset_rate_limits_clears_in_memory_buckets():
    now = datetime.now(timezone.utc)
    check_rate_limit("user_1", "generate", 1, now)
    with pytest.raises(RateLimitError):
        check_rate_limit("user_1", "generate", 1, now)

    reset_rate_limits()
    check_rate_limit("user_1", "generate", 1, now)


def test_prune_rate_limits_expires_old_buckets():
    start = datetime.now(timezone.utc)
    check_rate_limit("user_1", "generate", 1, start)

    prune_rate_limits(start + timedelta(minutes=2))
    check_rate_limit("user_1", "generate", 1, start + timedelta(minutes=2))
