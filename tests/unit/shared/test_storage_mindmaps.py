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


def test_mindmap_crud_roundtrip(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    try:
        storage.init_db()
        # 需要一个 user 满足外键
        with storage.connect() as conn:
            conn.execute(
                "INSERT INTO users (id, username, password_hash, created_at) "
                "VALUES ('u1','alice','x','2026-08-13T00:00:00+00:00')"
            )
        mid = storage.save_mindmap("u1", "现在完成时", "# 现在完成时\n## 结构\n- have+pp", "现在完成时")
        got = storage.get_mindmap("u1", mid)
        assert got is not None
        assert got["title"] == "现在完成时"
        assert got["outline_md"].startswith("# 现在完成时")

        rows = storage.list_mindmaps("u1")
        assert len(rows) == 1 and rows[0]["id"] == mid

        assert storage.update_mindmap("u1", mid, outline_md="# 改了", title="新名") is True
        got2 = storage.get_mindmap("u1", mid)
        assert got2["outline_md"] == "# 改了" and got2["title"] == "新名"

        # isolation
        assert storage.get_mindmap("u2", mid) is None
        assert storage.update_mindmap("u2", mid, title="x") is False
        assert storage.delete_mindmap("u2", mid) is False

        assert storage.delete_mindmap("u1", mid) is True
        assert storage.get_mindmap("u1", mid) is None
    finally:
        _teardown()
