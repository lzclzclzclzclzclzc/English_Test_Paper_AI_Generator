from __future__ import annotations

import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from shared import storage
from shared.config import get_config, reset_config_cache


def test_health_is_lightweight_and_public(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_reports_missing_question_bank(client):
    response = client.get("/api/health/ready")
    body = response.json()

    assert response.status_code == 503
    assert body["status"] == "not_ready"
    assert body["checks"]["sqlite"] is True
    assert body["checks"]["core_tables"] is True
    assert body["checks"]["question_bank"] is False
    assert body["checks"]["vector_bank"] is False


def test_readiness_accepts_real_question_bank_copy(tmp_path, monkeypatch):
    source_db = Path("data/questions.db")
    assert source_db.exists(), "real question bank database is required for this integration test"
    db_copy = tmp_path / "questions-copy.db"
    shutil.copyfile(source_db, db_copy)

    monkeypatch.setenv("BACKEND_ENV", "test")
    monkeypatch.setenv("BCRYPT_ROUNDS", "4")
    reset_config_cache()
    storage.set_db_path(db_copy)

    from backend.main import create_app

    try:
        get_config()
        with TestClient(create_app(), raise_server_exceptions=False) as real_db_client:
            response = real_db_client.get("/api/health/ready")
        body = response.json()
        assert response.status_code == 200
        assert body["status"] == "ready"
        assert body["checks"] == {
            "sqlite": True,
            "core_tables": True,
            "question_bank": True,
            "vector_bank": True,
        }
    finally:
        storage.set_db_path(None)
        reset_config_cache()
