from __future__ import annotations

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
            }
    except Exception:
        return {
            "sqlite": False,
            "core_tables": False,
            "question_bank": False,
        }


def _has_tables(conn, table_names: set[str]) -> bool:
    placeholders = ", ".join("?" for _ in table_names)
    rows = conn.execute(
        f"SELECT name FROM sqlite_master WHERE type = 'table' AND name IN ({placeholders})",
        tuple(table_names),
    ).fetchall()
    return {row["name"] for row in rows} == table_names


def _has_question_bank(conn) -> bool:
    table = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'questions'").fetchone()
    if table is None:
        return False
    row = conn.execute("SELECT COUNT(*) AS count FROM questions").fetchone()
    return int(row["count"]) > 0
