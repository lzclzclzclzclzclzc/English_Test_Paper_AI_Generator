from __future__ import annotations

import sqlite3
import json
from pathlib import Path

from backend.cli import _deploy_check, _smoke
from shared.config import reset_config_cache


def _table_count(db_path: Path, table: str) -> int | None:
    with sqlite3.connect(db_path) as conn:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        if not exists:
            return None
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_smoke_does_not_write_to_tracked_question_database():
    db_path = Path("data/questions.db")
    before = {table: _table_count(db_path, table) for table in ["users", "sessions", "papers", "attempts", "attempt_items"]}

    assert _smoke() == 0

    after = {table: _table_count(db_path, table) for table in ["users", "sessions", "papers", "attempts", "attempt_items"]}
    assert after == before


def test_deploy_check_reports_missing_deployment_prerequisites(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("BACKEND_ENV", "production")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    reset_config_cache()
    try:
        assert _deploy_check() == 2
        result = json.loads(capsys.readouterr().out)
        assert result["status"] == "not_ready"
        assert result["checks"]["production_mode"] is True
        assert result["checks"]["llm_api_key"] is False
        assert result["checks"]["static_index"] is False
    finally:
        reset_config_cache()
