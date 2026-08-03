from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from shared import storage

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness() -> JSONResponse:
    checks = _readiness_checks()
    ready = all(checks.values())
    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "ready" if ready else "not_ready",
            "checks": checks,
        },
    )


def _readiness_checks() -> dict[str, bool]:
    try:
        with storage.connect() as conn:
            conn.execute("SELECT 1").fetchone()
            return {
                "sqlite": True,
                "core_tables": _has_tables(
                    conn,
                    {
                        "users",
                        "sessions",
                        "papers",
                        "attempts",
                        "attempt_items",
                        "schema_migrations",
                    },
                ),
                "question_bank": _has_question_bank(conn),
                "vector_bank": _has_vector_bank(conn),
            }
    except Exception:
        return {
            "sqlite": False,
            "core_tables": False,
            "question_bank": False,
            "vector_bank": False,
        }


def _has_tables(conn, table_names: set[str]) -> bool:
    placeholders = ", ".join("?" for _ in table_names)
    rows = conn.execute(
        f"SELECT name FROM sqlite_master WHERE type = 'table' AND name IN ({placeholders})",
        tuple(table_names),
    ).fetchall()
    return {row["name"] for row in rows} == table_names


def _has_question_bank(conn) -> bool:
    if not _has_tables(conn, {"questions", "knowledge_points", "question_knowledge_points"}):
        return False

    question_columns = _table_columns(conn, "questions")
    required_question_columns = {
        "id",
        "book",
        "question_type",
        "chapter_l1",
        "chapter_l2",
        "number",
        "stem",
        "options_json",
        "hint",
        "original_sentence",
        "instruction",
        "template",
        "answer_json",
        "solution",
        "source_md",
        "source_line",
        "stem_hash",
        "created_at",
        "version",
    }
    if not required_question_columns.issubset(question_columns):
        return False
    if {"difficulty", "embedding_text"} & question_columns:
        return False

    kp_columns = _table_columns(conn, "knowledge_points")
    if not {"id", "level1", "level2", "aliases_json"}.issubset(kp_columns):
        return False
    if "parent_id" in kp_columns:
        return False

    qkp_columns = _table_columns(conn, "question_knowledge_points")
    if not {"question_id", "knowledge_point_id"}.issubset(qkp_columns):
        return False

    question_count = int(conn.execute("SELECT COUNT(*) AS count FROM questions").fetchone()["count"])
    kp_count = int(conn.execute("SELECT COUNT(*) AS count FROM knowledge_points").fetchone()["count"])
    qkp_count = int(conn.execute("SELECT COUNT(*) AS count FROM question_knowledge_points").fetchone()["count"])
    if question_count == 0 or kp_count == 0 or qkp_count == 0:
        return False

    missing_kp_rows = conn.execute(
        """
        SELECT q.id
        FROM questions q
        LEFT JOIN question_knowledge_points qkp ON qkp.question_id = q.id
        WHERE qkp.knowledge_point_id IS NULL
        LIMIT 1
        """
    ).fetchone()
    if missing_kp_rows is not None:
        return False

    sample_rows = conn.execute(
        "SELECT question_type, answer_json FROM questions ORDER BY id LIMIT 20"
    ).fetchall()
    try:
        for row in sample_rows:
            answer = json.loads(row["answer_json"])
            if row["question_type"] == "single_choice":
                if not isinstance(answer, str):
                    return False
            elif not isinstance(answer, list):
                return False
    except (TypeError, json.JSONDecodeError):
        return False

    return True


def _has_vector_bank(conn) -> bool:
    # Listening questions are intentionally SQLite-only (matched by exact SQL,
    # never semantic search), so they carry no embeddings. The vector bank is
    # expected to cover only the non-listening questions — count those.
    question_count = 0
    if _table_exists(conn, "questions"):
        row = conn.execute(
            "SELECT COUNT(*) AS count FROM questions WHERE question_type NOT LIKE 'listening%'"
        ).fetchone()
        question_count = int(row["count"])
    status = storage.inspect_chroma_question_collection(expected_question_count=question_count)
    return bool(status["ready"])


def _table_columns(conn, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def _table_exists(conn, table: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone() is not None
