from __future__ import annotations

from fastapi import APIRouter

from shared import storage

router = APIRouter(tags=["test"])


@router.get("/db-inspect")
async def db_inspect(table: str) -> dict[str, object]:
    if table not in {"users", "sessions", "papers", "attempts", "attempt_items"}:
        return {"rows": []}
    with storage.connect() as conn:
        rows = conn.execute(f"SELECT * FROM {table}").fetchall()
    return {"rows": [dict(row) for row in rows]}


@router.post("/llm-scripts")
async def llm_scripts() -> dict[str, str]:
    return {"status": "noop"}
