"""Read-only question-bank access used by the retriever."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from shared.schemas import Option, Question, QuestionType


class QuestionRepo:
    def __init__(self, db_path: Path) -> None:
        if not db_path.is_file():
            raise FileNotFoundError(f"question bank not found: {db_path}")
        self._db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _question(conn: sqlite3.Connection, row: sqlite3.Row) -> Question:
        kp_rows = conn.execute(
            "SELECT knowledge_point_id FROM question_knowledge_points "
            "WHERE question_id = ? ORDER BY knowledge_point_id", (row["id"],)
        ).fetchall()
        options = json.loads(row["options_json"]) if row["options_json"] else None
        return Question(
            id=row["id"], book=row["book"], question_type=row["question_type"],
            chapter_l1=row["chapter_l1"], chapter_l2=row["chapter_l2"], number=row["number"],
            stem=row["stem"], options=[Option.model_validate(x) for x in options] if options else None,
            hint=row["hint"], original_sentence=row["original_sentence"],
            instruction=row["instruction"], template=row["template"],
            answer=json.loads(row["answer_json"]), solution=row["solution"],
            knowledge_point_ids=[r["knowledge_point_id"] for r in kp_rows],
            source_md=row["source_md"], source_line=row["source_line"],
            stem_hash=row["stem_hash"], created_at=datetime.fromisoformat(row["created_at"]),
            version=row["version"],
        )

    def filter_ids(
        self, *, question_types: list[QuestionType] | None = None,
        knowledge_points: list[str] | None = None,
    ) -> list[str]:
        clauses: list[str] = []
        params: list[str] = []
        joins = ""
        if question_types:
            clauses.append("q.question_type IN (" + ",".join("?" * len(question_types)) + ")")
            params.extend(question_types)
        if knowledge_points:
            joins = " JOIN question_knowledge_points qkp ON qkp.question_id = q.id"
            clauses.append("qkp.knowledge_point_id IN (" + ",".join("?" * len(knowledge_points)) + ")")
            params.extend(knowledge_points)
        sql = "SELECT DISTINCT q.id FROM questions q" + joins
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY q.id"
        with self._connect() as conn:
            return [r["id"] for r in conn.execute(sql, params)]

    def get_by_ids(self, ids: list[str]) -> dict[str, Question]:
        if not ids:
            return {}
        placeholders = ",".join("?" * len(ids))
        with self._connect() as conn:
            rows = conn.execute(f"SELECT * FROM questions WHERE id IN ({placeholders})", ids).fetchall()
            return {row["id"]: self._question(conn, row) for row in rows}
