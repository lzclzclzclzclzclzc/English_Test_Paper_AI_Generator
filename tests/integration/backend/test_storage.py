from __future__ import annotations

from datetime import datetime, timezone

from shared import storage
from shared.schemas import Attempt, AttemptItem


def _attempt() -> Attempt:
    return Attempt(
        user_id="user_1",
        paper_id="paper_1",
        answered_at=datetime.now(timezone.utc),
        items=[
            AttemptItem(
                source_question_id="q_00001",
                knowledge_point_ids=["kp_1"],
                question_type="single_choice",
                is_correct=True,
            )
        ],
    )


def test_write_attempt_uses_current_attempt_items_schema(client):
    attempt_id = storage.write_attempt(_attempt())
    with storage.connect() as conn:
        row = conn.execute(
            "SELECT attempt_id, source_question_id, question_type, is_correct, kps_json FROM attempt_items WHERE attempt_id = ?",
            (attempt_id,),
        ).fetchone()
        columns = {column["name"] for column in conn.execute("PRAGMA table_info(attempt_items)")}
    assert row["source_question_id"] == "q_00001"
    assert row["is_correct"] == 1
    assert "difficulty" not in columns


def test_write_attempt_tolerates_legacy_attempt_items_difficulty_column(tmp_path):
    legacy_db = tmp_path / "legacy.db"
    storage.set_db_path(legacy_db)
    with storage.connect() as conn:
        conn.executescript(
            """
            CREATE TABLE attempts (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                paper_id TEXT NOT NULL,
                answered_at TIMESTAMP NOT NULL
            );
            CREATE TABLE attempt_items (
                attempt_id TEXT NOT NULL,
                source_question_id TEXT NOT NULL,
                question_type TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                is_correct INTEGER NOT NULL,
                kps_json TEXT NOT NULL,
                PRIMARY KEY (attempt_id, source_question_id)
            );
            """
        )
    attempt_id = storage.write_attempt(_attempt())
    with storage.connect() as conn:
        row = conn.execute("SELECT difficulty FROM attempt_items WHERE attempt_id = ?", (attempt_id,)).fetchone()
    assert row["difficulty"] == "unknown"
