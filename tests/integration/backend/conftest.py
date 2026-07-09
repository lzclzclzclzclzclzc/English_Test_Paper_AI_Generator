from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from shared import storage
from shared.config import get_config, reset_config_cache


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "backend-test.db"
    storage.set_db_path(db_path)
    reset_config_cache()
    monkeypatch.setenv("BACKEND_ENV", "test")
    monkeypatch.setenv("BCRYPT_ROUNDS", "4")
    get_config()
    from backend.main import create_app

    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    storage.set_db_path(None)
    reset_config_cache()


@pytest.fixture
def logged_in_client(client):
    response = client.post("/api/auth/register", json={"username": "demo", "password": "demo123"})
    assert response.status_code == 200
    return client


@pytest.fixture
def generated_paper(logged_in_client):
    response = logged_in_client.post("/api/papers/generate", json={"user_query": "来 3 道中等难度英语题", "mode": "fresh"})
    assert response.status_code == 200
    return response.json()
