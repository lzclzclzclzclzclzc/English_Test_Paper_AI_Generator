from __future__ import annotations

import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from shared import storage
from shared.config import reset_config_cache


def test_backend_flow_against_copied_real_question_bank(tmp_path, monkeypatch):
    source_db = Path("data/questions.db")
    assert source_db.exists(), "real question bank database is required for this integration test"
    db_copy = tmp_path / "questions-copy.db"
    shutil.copyfile(source_db, db_copy)

    monkeypatch.setenv("BACKEND_ENV", "test")
    monkeypatch.setenv("BCRYPT_ROUNDS", "4")
    reset_config_cache()
    storage.set_db_path(db_copy)

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

        with storage.connect() as conn:
            question_count = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
            kp_count = conn.execute("SELECT COUNT(*) FROM knowledge_points").fetchone()[0]
            qkp_count = conn.execute("SELECT COUNT(*) FROM question_knowledge_points").fetchone()[0]
            question_columns = {row["name"] for row in conn.execute("PRAGMA table_info(questions)")}
            kp_columns = {row["name"] for row in conn.execute("PRAGMA table_info(knowledge_points)")}
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
        assert attempt_count == 1
        assert "difficulty" not in attempt_item_columns
        assert users_table is not None
        assert papers_table is not None
        assert migration_count >= 1
    finally:
        storage.set_db_path(None)
        reset_config_cache()
