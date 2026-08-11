from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from shared import storage
from shared.config import get_config, reset_config_cache


def _require_real_question_bank() -> Path:
    path = Path("data/questions.db")
    if not path.exists():
        pytest.skip("real question-bank artifact is not installed; see docs/data-artifacts.md")
    try:
        with sqlite3.connect(path) as conn:
            question_count = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    except sqlite3.DatabaseError:
        pytest.skip("real question-bank artifact is not installed; see docs/data-artifacts.md")
    if question_count == 0:
        pytest.skip("real question-bank artifact is not installed; see docs/data-artifacts.md")
    return path


def test_health_is_lightweight_and_public(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_development_cors_allows_configured_frontend_origin(tmp_path, monkeypatch):
    db_path = tmp_path / "cors-test.db"
    storage.set_db_path(db_path)
    monkeypatch.setenv("BACKEND_ENV", "development")
    monkeypatch.setenv("FRONTEND_ORIGIN", "http://127.0.0.1:5173")
    reset_config_cache()

    from backend.main import create_app

    try:
        with TestClient(create_app()) as development_client:
            response = development_client.options(
                "/api/auth/login",
                headers={
                    "Origin": "http://127.0.0.1:5173",
                    "Access-Control-Request-Method": "POST",
                },
            )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
        assert response.headers["access-control-allow-credentials"] == "true"
    finally:
        storage.set_db_path(None)
        reset_config_cache()


def test_test_mode_cors_allows_configured_frontend_origin(tmp_path, monkeypatch):
    db_path = tmp_path / "cors-test-mode.db"
    storage.set_db_path(db_path)
    monkeypatch.setenv("BACKEND_ENV", "test")
    monkeypatch.setenv("FRONTEND_ORIGIN", "http://localhost:4173")
    reset_config_cache()

    from backend.main import create_app

    try:
        with TestClient(create_app()) as test_client:
            response = test_client.options(
                "/api/auth/login",
                headers={
                    "Origin": "http://localhost:4173",
                    "Access-Control-Request-Method": "POST",
                },
            )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://localhost:4173"
        assert response.headers["access-control-allow-credentials"] == "true"
    finally:
        storage.set_db_path(None)
        reset_config_cache()


def test_production_serves_frontend_and_api_from_same_origin(tmp_path, monkeypatch):
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<main>frontend ready</main>", encoding="utf-8")
    storage.set_db_path(tmp_path / "same-origin.db")
    monkeypatch.setenv("BACKEND_ENV", "production")
    monkeypatch.setenv("BACKEND_STATIC_DIR", str(static_dir))
    reset_config_cache()

    from backend.main import create_app

    try:
        with TestClient(create_app()) as production_client:
            page = production_client.get("/")
            health = production_client.get("/api/health")
        assert page.status_code == 200
        assert "frontend ready" in page.text
        assert health.status_code == 200
    finally:
        storage.set_db_path(None)
        reset_config_cache()


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
    source_db = _require_real_question_bank()
    db_copy = tmp_path / "questions-copy.db"
    shutil.copyfile(source_db, db_copy)

    app_db = tmp_path / "app.db"
    monkeypatch.setenv("BACKEND_ENV", "test")
    monkeypatch.setenv("BCRYPT_ROUNDS", "4")
    monkeypatch.setenv("SQLITE_PATH", str(db_copy))
    monkeypatch.setenv("APP_DB_PATH", str(app_db))
    reset_config_cache()
    storage.set_db_path(app_db)
    storage.set_bank_db_path(db_copy)

    from backend.main import create_app

    try:
        get_config()
        storage.init_db()  # belt-and-suspenders: create_app() also inits the app DB
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
        storage.set_bank_db_path(None)
        reset_config_cache()
