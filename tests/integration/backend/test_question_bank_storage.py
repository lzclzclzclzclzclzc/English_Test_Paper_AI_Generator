from __future__ import annotations

import shutil
from pathlib import Path

from shared import storage


def test_read_question_bank_records_from_real_database_copy(tmp_path):
    db_copy = tmp_path / "questions-copy.db"
    shutil.copyfile(Path("data/questions.db"), db_copy)
    storage.set_db_path(db_copy)
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
        storage.set_db_path(None)


def test_read_knowledge_points_and_write_solution_on_database_copy(tmp_path):
    db_copy = tmp_path / "questions-copy.db"
    shutil.copyfile(Path("data/questions.db"), db_copy)
    storage.set_db_path(db_copy)
    try:
        kps = storage.list_knowledge_points()
        assert len(kps) == 49
        assert {kp.level1 for kp in kps} == {"single_choice", "word_form", "sentence_rewriting"}

        assert storage.write_question_solution("q_00001", "解析内容") is True
        assert storage.write_question_solution("q_00001", "不会覆盖") is False
        assert storage.get_question("q_00001").solution == "解析内容"
    finally:
        storage.set_db_path(None)
