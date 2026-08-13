from __future__ import annotations

from shared import storage
from shared.config import reset_config_cache


def _setup(tmp_path, monkeypatch):
    app = tmp_path / "app.db"
    bank = tmp_path / "bank.db"
    monkeypatch.setenv("APP_DB_PATH", str(app))
    monkeypatch.setenv("SQLITE_PATH", str(bank))
    reset_config_cache()
    storage.set_db_path(app)
    storage.set_bank_db_path(bank)


def _teardown():
    storage.set_db_path(None)
    storage.set_bank_db_path(None)
    reset_config_cache()


def test_mindmaps_table_created(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    try:
        storage.init_db()
        with storage.connect() as conn:
            assert storage._table_exists(conn, "mindmaps")
            cols = storage._table_columns(conn, "mindmaps")
            assert {"id", "user_id", "created_at", "updated_at",
                    "title", "knowledge_point", "outline_md"} <= cols
    finally:
        _teardown()
