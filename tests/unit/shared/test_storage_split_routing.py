from __future__ import annotations

import sqlite3

from shared import storage
from shared.config import reset_config_cache


def _make_bank(path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE questions (id TEXT PRIMARY KEY, book TEXT, question_type TEXT,
            chapter_l1 TEXT, chapter_l2 TEXT, number TEXT, stem TEXT,
            options_json TEXT, hint TEXT, original_sentence TEXT, instruction TEXT,
            template TEXT, answer_json TEXT, solution TEXT, source_md TEXT,
            source_line INTEGER, created_at TIMESTAMP, version INTEGER);
        CREATE TABLE knowledge_points (id TEXT PRIMARY KEY, level1 TEXT, level2 TEXT, aliases_json TEXT);
        CREATE TABLE question_knowledge_points (question_id TEXT, knowledge_point_id TEXT);
        INSERT INTO knowledge_points VALUES ('kp1','single_choice','一般现在时','[]');
        INSERT INTO questions VALUES ('q1','b','single_choice','l1','l2','1','stem',
            NULL,NULL,NULL,NULL,NULL,'"B"',NULL,'m.md',1,'2026-01-01T00:00:00+00:00',1);
        INSERT INTO question_knowledge_points VALUES ('q1','kp1');
        """
    )
    conn.commit()
    conn.close()


def test_bank_reads_hit_bank_not_app(tmp_path, monkeypatch):
    bank = tmp_path / "bank.db"
    app = tmp_path / "app.db"
    _make_bank(bank)
    monkeypatch.setenv("SQLITE_PATH", str(bank))
    monkeypatch.setenv("APP_DB_PATH", str(app))
    reset_config_cache()
    storage.set_db_path(app)
    storage.set_bank_db_path(bank)
    try:
        assert storage.get_question("q1") is not None
        assert [kp.id for kp in storage.list_knowledge_points()] == ["kp1"]
        assert len(storage.list_questions()) == 1
        assert storage.get_db_path() == app
    finally:
        storage.set_db_path(None)
        storage.set_bank_db_path(None)
        reset_config_cache()


def test_app_writes_do_not_create_bank_tables(tmp_path, monkeypatch):
    bank = tmp_path / "bank.db"
    app = tmp_path / "app.db"
    _make_bank(bank)
    monkeypatch.setenv("SQLITE_PATH", str(bank))
    monkeypatch.setenv("APP_DB_PATH", str(app))
    monkeypatch.setenv("BCRYPT_ROUNDS", "4")
    reset_config_cache()
    storage.set_db_path(app)
    storage.set_bank_db_path(bank)
    try:
        storage.create_user("alice", "hash")
        with storage.connect() as conn:
            names = {r["name"] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
        assert "users" in names
        assert "questions" not in names
    finally:
        storage.set_db_path(None)
        storage.set_bank_db_path(None)
        reset_config_cache()
