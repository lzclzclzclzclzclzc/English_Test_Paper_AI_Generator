"""Read-only access to the SQLite question bank for ai_engine.

Turns `questions` rows (+ their KP links) into `shared.schemas.Question`
objects. This is the ai_engine side of the storage boundary — ingestion
writes, ai_engine reads (Spec A §3.12). A future `shared/storage.py` may
absorb this; for now it lives here so Retriever/Analyzer can share it.

All queries are read-only. Connections are opened per call and closed;
the bank is tiny (~1k rows) so there's no pooling concern.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from shared.schemas import Option, Question, QuestionType

DEFAULT_DB_PATH = Path("data/questions.db")


def _row_to_question(row: sqlite3.Row, kp_ids: list[str]) -> Question:
    """Deserialise one `questions` row (+ its KP ids) into a Question."""
    options = None
    if row["options_json"]:
        options = [Option(**o) for o in json.loads(row["options_json"])]
    return Question(
        id=row["id"],
        book=row["book"],
        question_type=row["question_type"],
        chapter_l1=row["chapter_l1"],
        chapter_l2=row["chapter_l2"],
        number=row["number"],
        stem=row["stem"],
        options=options,
        hint=row["hint"],
        original_sentence=row["original_sentence"],
        instruction=row["instruction"],
        template=row["template"],
        answer=json.loads(row["answer_json"]),
        solution=row["solution"],
        knowledge_point_ids=kp_ids,
        source_md=row["source_md"],
        source_line=row["source_line"],
        created_at=row["created_at"],
        version=row["version"],
    )


class QuestionRepo:
    """Read-only question bank accessor."""

    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        if not db_path.is_file():
            raise FileNotFoundError(f"question bank not found: {db_path}")
        self._db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ─── KP links ────────────────────────────────────────────────────
    def _kp_map(self, conn: sqlite3.Connection, question_ids: list[str]) -> dict[str, list[str]]:
        """question_id → [kp_id, ...] for the given ids (stable order)."""
        if not question_ids:
            return {}
        placeholders = ",".join("?" * len(question_ids))
        out: dict[str, list[str]] = {}
        for r in conn.execute(
            f"SELECT question_id, knowledge_point_id "
            f"FROM question_knowledge_points "
            f"WHERE question_id IN ({placeholders}) "
            f"ORDER BY question_id, knowledge_point_id",
            question_ids,
        ):
            out.setdefault(r["question_id"], []).append(r["knowledge_point_id"])
        return out

    # ─── Fetch by id ─────────────────────────────────────────────────
    def get_by_ids(self, ids: list[str]) -> dict[str, Question]:
        """Fetch questions by id. Returns id → Question (missing ids omitted).

        Order is not guaranteed — caller re-orders (e.g. by vector score).
        """
        if not ids:
            return {}
        conn = self._connect()
        try:
            kp_map = self._kp_map(conn, ids)
            placeholders = ",".join("?" * len(ids))
            out: dict[str, Question] = {}
            for row in conn.execute(
                f"SELECT * FROM questions WHERE id IN ({placeholders})", ids
            ):
                out[row["id"]] = _row_to_question(row, kp_map.get(row["id"], []))
            return out
        finally:
            conn.close()

    # ─── Attribute filter (SQL hard filter) ──────────────────────────
    def filter_ids(
        self,
        *,
        question_types: list[QuestionType] | None = None,
        knowledge_points: list[str] | None = None,
        book: str | None = None,
    ) -> list[str]:
        """Return question ids matching the attribute filters (AND across
        fields, OR within a field). Empty/None filter = unrestricted on that
        field. Result ordered by id for determinism.

        KP filter uses a join against question_knowledge_points: a question
        matches if it carries ANY of the requested KP ids.
        """
        conn = self._connect()
        try:
            where: list[str] = []
            params: list[object] = []

            if question_types:
                where.append(
                    f"q.question_type IN ({','.join('?' * len(question_types))})"
                )
                params.extend(question_types)
            if book:
                where.append("q.book = ?")
                params.append(book)

            if knowledge_points:
                kp_ph = ",".join("?" * len(knowledge_points))
                sql = (
                    f"SELECT DISTINCT q.id FROM questions q "
                    f"JOIN question_knowledge_points qk ON q.id = qk.question_id "
                    f"WHERE qk.knowledge_point_id IN ({kp_ph})"
                )
                params_kp = list(knowledge_points)
                if where:
                    sql += " AND " + " AND ".join(where)
                    params_kp.extend(params)
                sql += " ORDER BY q.id"
                return [r["id"] for r in conn.execute(sql, params_kp)]

            sql = "SELECT q.id FROM questions q"
            if where:
                sql += " WHERE " + " AND ".join(where)
            sql += " ORDER BY q.id"
            return [r["id"] for r in conn.execute(sql, params)]
        finally:
            conn.close()

    def count(self) -> int:
        conn = self._connect()
        try:
            return conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        finally:
            conn.close()
