from __future__ import annotations

import json

from shared import storage
from shared.config import reset_config_cache
from agent import tools


def _setup(tmp_path, monkeypatch):
    app = tmp_path / "app.db"
    bank = tmp_path / "bank.db"
    monkeypatch.setenv("APP_DB_PATH", str(app))
    monkeypatch.setenv("SQLITE_PATH", str(bank))
    reset_config_cache()
    storage.set_db_path(app)
    storage.set_bank_db_path(bank)
    storage.init_db()
    with storage.connect() as conn:
        conn.execute(
            "INSERT INTO users (id, username, password_hash, created_at) "
            "VALUES ('u1','alice','x','2026-08-13T00:00:00+00:00')"
        )


def _teardown():
    storage.set_db_path(None)
    storage.set_bank_db_path(None)
    tools.set_current_user_id(None)
    tools.set_current_mindmap_id(None)
    reset_config_cache()


def test_create_and_update_current_mindmap(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    try:
        tools.set_current_user_id("u1")
        out = json.loads(tools._create_mindmap("现在完成时", "# 现在完成时\n## 结构"))
        mid = out["mindmap_id"]
        assert out["title"] == "现在完成时"

        tools.set_current_mindmap_id(mid)
        got = json.loads(tools._get_current_mindmap())
        assert got["outline_markdown"].startswith("# 现在完成时")

        upd = json.loads(tools._update_current_mindmap("# 现在完成时\n## 结构\n## 用法"))
        assert upd["ok"] is True
        assert storage.get_mindmap("u1", mid)["outline_md"].endswith("## 用法")
    finally:
        _teardown()


def test_create_mindmap_rejects_empty_outline(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    try:
        tools.set_current_user_id("u1")
        out = json.loads(tools._create_mindmap("空", "   "))
        assert "error" in out
    finally:
        _teardown()
