from __future__ import annotations

import sqlite3

from shared import storage
from shared.config import reset_config_cache
from agent import tools


def _make_bank(path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE questions (id TEXT PRIMARY KEY, question_type TEXT, stem TEXT,
            options_json TEXT, hint TEXT, original_sentence TEXT, instruction TEXT,
            template TEXT, answer_json TEXT);
        CREATE TABLE knowledge_points (id TEXT PRIMARY KEY, level1 TEXT, level2 TEXT, aliases_json TEXT);
        CREATE TABLE question_knowledge_points (question_id TEXT, knowledge_point_id TEXT);
        INSERT INTO knowledge_points VALUES ('kp1','single_choice','一般现在时','[]');
        INSERT INTO questions VALUES ('q1','single_choice','stem',NULL,NULL,NULL,NULL,NULL,'"B"');
        INSERT INTO question_knowledge_points VALUES ('q1','kp1');
        """
    )
    conn.commit()
    conn.close()


def _call_example_questions(kp_id, count):
    """Call the underlying (unwrapped) plain function of the tool.

    @function_tool wraps get_example_questions in an agents.tool.FunctionTool,
    which exposes no clean sync plain-callable (only the async on_invoke_tool).
    So the tool body was extracted into tools._example_questions for testing.
    """
    return tools._example_questions(kp_id, count)


def test_get_example_questions_reads_bank(tmp_path, monkeypatch):
    bank = tmp_path / "bank.db"
    app = tmp_path / "app.db"
    _make_bank(bank)
    monkeypatch.setenv("SQLITE_PATH", str(bank))
    monkeypatch.setenv("APP_DB_PATH", str(app))
    reset_config_cache()
    storage.set_db_path(app)
    storage.set_bank_db_path(bank)
    try:
        out = _call_example_questions("kp1", 3)
        assert "q1" in out
    finally:
        storage.set_db_path(None)
        storage.set_bank_db_path(None)
        reset_config_cache()
