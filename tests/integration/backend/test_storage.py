from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from backend.schemas import StoredAttempt, StoredAttemptItem
from shared import storage
from shared.schemas import GenerateRequest, Paper, PaperItem, RevisedQuestion


def _attempt() -> StoredAttempt:
    return StoredAttempt(
        user_id="user_1",
        paper_id="paper_1",
        answered_at=datetime.now(timezone.utc),
        items=[
            StoredAttemptItem(
                index=1,
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
            """
            SELECT attempt_id, item_index, source_question_id, question_type, is_correct, kps_json
            FROM attempt_items
            WHERE attempt_id = ?
            """,
            (attempt_id,),
        ).fetchone()
        table_info = conn.execute("PRAGMA table_info(attempt_items)").fetchall()
        columns = {column["name"] for column in table_info}
        primary_key_columns = [column["name"] for column in sorted(table_info, key=lambda column: column["pk"]) if column["pk"]]
    assert row["item_index"] == 1
    assert row["source_question_id"] == "q_00001"
    assert row["is_correct"] == 1
    assert primary_key_columns == ["attempt_id", "item_index"]
    assert "difficulty" not in columns


def test_write_attempt_allows_repeated_source_question_ids(client):
    attempt = _attempt().model_copy(
        update={
            "items": [
                StoredAttemptItem(
                    index=1,
                    source_question_id="q_reused",
                    knowledge_point_ids=["kp_1"],
                    question_type="single_choice",
                    is_correct=True,
                ),
                StoredAttemptItem(
                    index=2,
                    source_question_id="q_reused",
                    knowledge_point_ids=["kp_2"],
                    question_type="single_choice",
                    is_correct=False,
                ),
            ]
        }
    )
    attempt_id = storage.write_attempt(attempt)
    with storage.connect() as conn:
        rows = conn.execute(
            """
            SELECT item_index, source_question_id, is_correct
            FROM attempt_items
            WHERE attempt_id = ?
            ORDER BY item_index
            """,
            (attempt_id,),
        ).fetchall()
    assert [row["item_index"] for row in rows] == [1, 2]
    assert {row["source_question_id"] for row in rows} == {"q_reused"}


def test_write_attempt_and_mark_paper_submitted_rolls_back_together(client):
    user = storage.create_user("txn_user", "hash")
    paper = Paper(
        paper_id="paper_1",
        title="test paper",
        generated_at=datetime.now(timezone.utc),
        request=GenerateRequest(total_questions=2),
        items=[
            PaperItem(
                index=1,
                source_question_id="q_00001",
                revision_mode="original",
                question=RevisedQuestion(question_type="single_choice", answer="A"),
            )
        ],
    )
    storage.save_paper(paper, user.id)
    attempt = StoredAttempt(
        user_id=user.id,
        paper_id=paper.paper_id,
        answered_at=datetime.now(timezone.utc),
        items=[
            StoredAttemptItem(
                index=1,
                source_question_id="q_00001",
                knowledge_point_ids=["kp_1"],
                question_type="single_choice",
                is_correct=True,
            ),
            StoredAttemptItem(
                index=1,
                source_question_id="q_00002",
                knowledge_point_ids=["kp_2"],
                question_type="single_choice",
                is_correct=False,
            ),
        ],
    )

    try:
        storage.write_attempt_and_mark_paper_submitted(attempt)
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError("duplicate attempt item index should fail")

    with storage.connect() as conn:
        attempt_count = conn.execute("SELECT COUNT(*) AS count FROM attempts WHERE paper_id = ?", (paper.paper_id,)).fetchone()
        paper_row = conn.execute("SELECT submitted, submitted_at FROM papers WHERE paper_id = ?", (paper.paper_id,)).fetchone()
    assert attempt_count["count"] == 0
    assert paper_row["submitted"] == 0
    assert paper_row["submitted_at"] is None


def test_init_db_records_applied_migrations(client):
    storage.init_db()
    storage.init_db()
    with storage.connect() as conn:
        rows = conn.execute("SELECT id FROM schema_migrations ORDER BY id").fetchall()
    assert [row["id"] for row in rows] == [
        storage.MIGRATION_ATTEMPT_ITEMS_ITEM_INDEX,
        storage.MIGRATION_USERS_ROLE,
        storage.MIGRATION_USERS_STATUS,
    ]


def test_init_db_migrates_legacy_attempt_items_difficulty_column(tmp_path):
    legacy_db = tmp_path / "legacy.db"
    storage.set_db_path(legacy_db)
    try:
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
            conn.execute(
                "INSERT INTO attempts (id, user_id, paper_id, answered_at) VALUES (?, ?, ?, ?)",
                ("legacy_attempt", "user_1", "paper_1", datetime.now(timezone.utc).isoformat()),
            )
            conn.execute(
                """
                INSERT INTO attempt_items
                    (attempt_id, source_question_id, question_type, difficulty, is_correct, kps_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("legacy_attempt", "q_legacy", "single_choice", "unknown", 1, '["kp_legacy"]'),
            )
        storage.init_db()
        with storage.connect() as conn:
            table_info = conn.execute("PRAGMA table_info(attempt_items)").fetchall()
            migrated_row = conn.execute(
                """
                SELECT item_index, source_question_id, question_type, is_correct, kps_json
                FROM attempt_items
                WHERE attempt_id = ?
                """,
                ("legacy_attempt",),
            ).fetchone()
            migration_row = conn.execute(
                "SELECT id FROM schema_migrations WHERE id = ?",
                (storage.MIGRATION_ATTEMPT_ITEMS_ITEM_INDEX,),
            ).fetchone()
    finally:
        storage.set_db_path(None)
    columns = {column["name"] for column in table_info}
    primary_key_columns = [column["name"] for column in sorted(table_info, key=lambda column: column["pk"]) if column["pk"]]
    assert "item_index" in columns
    assert "difficulty" not in columns
    assert primary_key_columns == ["attempt_id", "item_index"]
    assert migrated_row["item_index"] == 1
    assert migrated_row["source_question_id"] == "q_legacy"
    assert migrated_row["kps_json"] == '["kp_legacy"]'
    assert migration_row["id"] == storage.MIGRATION_ATTEMPT_ITEMS_ITEM_INDEX
