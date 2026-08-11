from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest

from shared import storage


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


def test_read_question_bank_records_from_real_database_copy(tmp_path):
    db_copy = tmp_path / "questions-copy.db"
    shutil.copyfile(_require_real_question_bank(), db_copy)
    storage.set_bank_db_path(db_copy)
    try:
        q = storage.get_question("q_00001")
        assert q is not None
        assert q.question_type == "single_choice"
        assert q.answer == "B"
        assert q.options and q.options[1].label == "B"
        assert q.knowledge_point_ids

        by_type = storage.list_questions(question_type="word_form", limit=3)
        assert len(by_type) == 3
        assert {item.question_type for item in by_type} == {"word_form"}

        by_kp = storage.list_questions(knowledge_point_ids=[q.knowledge_point_ids[0]], limit=5)
        assert any(item.id == q.id for item in by_kp)
    finally:
        storage.set_bank_db_path(None)


def test_read_knowledge_points_and_write_solution_on_database_copy(tmp_path):
    db_copy = tmp_path / "questions-copy.db"
    shutil.copyfile(_require_real_question_bank(), db_copy)
    storage.set_bank_db_path(db_copy)
    try:
        kps = storage.list_knowledge_points()
        assert kps
        assert {"single_choice", "word_form", "sentence_rewriting"}.issubset({kp.level1 for kp in kps})

        assert storage.write_question_solution("q_00001", "解析内容") is True
        assert storage.write_question_solution("q_00001", "不会覆盖") is False
        assert storage.get_question("q_00001").solution == "解析内容"
    finally:
        storage.set_bank_db_path(None)
