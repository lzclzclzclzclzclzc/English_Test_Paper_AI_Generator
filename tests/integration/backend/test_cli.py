from __future__ import annotations

import sqlite3
from pathlib import Path

from backend.cli import _smoke


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
