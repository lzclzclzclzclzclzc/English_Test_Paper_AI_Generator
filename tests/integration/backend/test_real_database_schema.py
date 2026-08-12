from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.services import ai_gateway
from shared import storage
from shared.config import reset_config_cache
from shared.schemas import VECTOR_INDEXED_QUESTION_TYPES
from tests.integration.backend.conftest import _fake_paper


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


def _require_real_chroma() -> Path:
    path = Path("data/chroma/chroma.sqlite3")
    if not path.exists():
        pytest.skip("real Chroma artifact is not installed; see docs/data-artifacts.md")
    return path


def test_backend_flow_against_copied_real_question_bank(tmp_path, monkeypatch):
    source_db = _require_real_question_bank()
    db_copy = tmp_path / "questions-copy.db"
    shutil.copyfile(source_db, db_copy)
    app_db = tmp_path / "app.db"

    monkeypatch.setenv("BACKEND_ENV", "test")
    monkeypatch.setenv("BCRYPT_ROUNDS", "4")
    monkeypatch.setenv("SQLITE_PATH", str(db_copy))   # bank = copied real questions.db
    monkeypatch.setenv("APP_DB_PATH", str(app_db))     # user data = fresh temp file
    monkeypatch.setattr(ai_gateway, "generate_paper", _fake_paper)
    reset_config_cache()
    storage.set_db_path(app_db)
    storage.set_bank_db_path(db_copy)

    from backend.main import create_app

    try:
        with TestClient(create_app(), raise_server_exceptions=False) as client:
            response = client.post("/api/auth/register", json={"username": "realdb", "password": "demo123"})
            assert response.status_code == 200

            paper = client.post(
                "/api/papers/generate",
                json={"user_query": "来 3 道中等难度英语题", "mode": "fresh"},
            )
            assert paper.status_code == 200
            paper_body = paper.json()

            grade = client.post(
                "/api/attempts",
                json={
                    "paper_id": paper_body["paper_id"],
                    "items": [
                        {"index": 1, "user_answer": "B"},
                        {"index": 2, "user_answer": "written"},
                        {"index": 3, "user_answer": {"blank1": "so", "blank2": "that"}},
                    ],
                },
            )
            assert grade.status_code == 200
            assert client.get("/api/users/me/mastery").status_code == 200

        with storage.connect_bank() as conn:
            question_count = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
            kp_count = conn.execute("SELECT COUNT(*) FROM knowledge_points").fetchone()[0]
            qkp_count = conn.execute("SELECT COUNT(*) FROM question_knowledge_points").fetchone()[0]
            question_columns = {row["name"] for row in conn.execute("PRAGMA table_info(questions)")}
            kp_columns = {row["name"] for row in conn.execute("PRAGMA table_info(knowledge_points)")}

        with storage.connect() as conn:
            attempt_count = conn.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]
            attempt_item_columns = {row["name"] for row in conn.execute("PRAGMA table_info(attempt_items)")}
            users_table = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'").fetchone()
            papers_table = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='papers'").fetchone()
            migration_count = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]

        assert question_count > 0
        assert kp_count > 0
        assert qkp_count >= question_count
        assert {
            "id",
            "book",
            "question_type",
            "chapter_l1",
            "chapter_l2",
            "number",
            "answer_json",
            "source_md",
            "source_line",
            "stem_hash",
        }.issubset(question_columns)
        assert "difficulty" not in question_columns
        assert "embedding_text" not in question_columns
        assert {"id", "level1", "level2", "aliases_json"}.issubset(kp_columns)
        assert "parent_id" not in kp_columns
        # fresh app.db + exactly one graded paper in this test → exactly one attempt
        assert attempt_count == 1
        assert "difficulty" not in attempt_item_columns
        assert users_table is not None
        assert papers_table is not None
        assert migration_count >= 1
    finally:
        storage.set_db_path(None)
        storage.set_bank_db_path(None)
        reset_config_cache()


def test_chroma_artifact_matches_real_question_bank_shape():
    sqlite_db = _require_real_question_bank()
    chroma_db = _require_real_chroma()

    # The vector store covers ONLY the semantically-searchable types; every
    # other type is SQL-only and carries no embedding, so the expected vector
    # count is the count of the indexed types, not the whole bank.
    with sqlite3.connect(sqlite_db) as conn:
        total_count = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        placeholders = ", ".join("?" for _ in VECTOR_INDEXED_QUESTION_TYPES)
        indexed_count = conn.execute(
            f"SELECT COUNT(*) FROM questions WHERE question_type IN ({placeholders})",
            tuple(VECTOR_INDEXED_QUESTION_TYPES),
        ).fetchone()[0]

    status = storage.inspect_chroma_question_collection(expected_question_count=indexed_count)

    assert total_count > 0
    assert indexed_count > 0
    assert status["ready"] is True
    assert status["collection"] == "questions"
    assert status["dimension"] == 2560
    assert status["embedding_count"] == indexed_count
    assert {
        "book",
        "chapter_l1",
        "chapter_l2",
        "chroma:document",
        "kp_ids",
        "question_type",
    }.issubset(set(status["metadata_keys"]))
    assert "difficulty" not in status["metadata_keys"]
