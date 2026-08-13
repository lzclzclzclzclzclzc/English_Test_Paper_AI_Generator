from __future__ import annotations

import json
import math
import secrets
import sqlite3
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator, Literal
from uuid import uuid4

from backend.schemas import PaperListItem, Session, StoredAttempt, User, UserRecord
from shared.config import get_config
from shared.schemas import (
    KPMastery,
    KnowledgePoint,
    MasteryProfile,
    Option,
    Paper,
    Question,
)

DB_PATH_OVERRIDE: Path | None = None
BANK_DB_PATH_OVERRIDE: Path | None = None
MIGRATION_ATTEMPT_ITEMS_ITEM_INDEX = "20260709_001_attempt_items_item_index"
MIGRATION_USERS_ROLE = "20260801_001_users_role"
MIGRATION_USERS_STATUS = "20260801_002_users_status"
MIGRATION_ATTEMPT_ITEMS_USER_ANSWER = "20260803_001_attempt_items_user_answer"
MIGRATION_WRITING_GRADE_RESULTS = "20260806_001_writing_grade_results"
MIGRATION_VOCABULARY_SCHEMA = "20260730_001_vocabulary_mvp"
MIGRATION_VOCABULARY_RETRY_QUEUE = "20260804_001_vocabulary_retry_queue"
MIGRATION_VOCABULARY_WORD_SOURCES = "20260805_001_vocabulary_word_sources"
MIGRATION_MINDMAPS = "20260813_001_mindmaps"
# Windows' bundled Python may not ship IANA zone data. Shanghai has no DST, so
# the explicit UTC+08:00 offset keeps daily quota and streak boundaries stable.
VOCABULARY_TIMEZONE = timezone(timedelta(hours=8), name="Asia/Shanghai")
VOCABULARY_INTERVALS = (1, 3, 7, 14, 30)
DEFAULT_DAILY_NEW_LIMIT = 20
CHROMA_COLLECTION_NAME = "questions"
CHROMA_REQUIRED_METADATA_KEYS = {
    "book",
    "chapter_l1",
    "chapter_l2",
    "chroma:document",
    "kp_ids",
    "question_type",
}


def set_db_path(path: str | Path | None) -> None:
    global DB_PATH_OVERRIDE
    DB_PATH_OVERRIDE = Path(path) if path is not None else None


def get_db_path() -> Path:
    # This is the APP/user DB (users, papers, attempts, …). The question bank
    # lives at config.db_path — reached via get_bank_db_path()/connect_bank().
    return DB_PATH_OVERRIDE or get_config().app_db_path


def get_chroma_path() -> Path:
    return get_config().chroma_path


def set_bank_db_path(path: str | Path | None) -> None:
    global BANK_DB_PATH_OVERRIDE
    BANK_DB_PATH_OVERRIDE = Path(path) if path is not None else None


def get_bank_db_path() -> Path:
    return BANK_DB_PATH_OVERRIDE or get_config().db_path


@contextmanager
def connect_bank() -> Iterator[sqlite3.Connection]:
    """Read-only-in-practice connection to the question bank DB.

    The bank is built offline by ingestion; the app never creates its tables,
    so — unlike connect() — this does not run init_db()/migrations. Callers
    guard with _table_exists() for the not-yet-built case.
    """
    path = get_bank_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    path = get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        _ensure_schema_migrations(conn)
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id),
                created_at TIMESTAMP NOT NULL,
                expires_at TIMESTAMP NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
            CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);

            CREATE TABLE IF NOT EXISTS papers (
                paper_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id),
                title TEXT NOT NULL,
                generated_at TIMESTAMP NOT NULL,
                payload_json TEXT NOT NULL,
                submitted INTEGER NOT NULL DEFAULT 0,
                submitted_at TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_papers_user ON papers(user_id);
            CREATE INDEX IF NOT EXISTS idx_papers_generated ON papers(generated_at);

            CREATE TABLE IF NOT EXISTS attempts (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                paper_id TEXT NOT NULL,
                answered_at TIMESTAMP NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_att_user ON attempts(user_id);
            CREATE INDEX IF NOT EXISTS idx_att_answered ON attempts(answered_at);
            CREATE INDEX IF NOT EXISTS idx_att_paper ON attempts(paper_id);

            CREATE TABLE IF NOT EXISTS attempt_items (
                attempt_id TEXT NOT NULL REFERENCES attempts(id),
                item_index INTEGER NOT NULL,
                source_question_id TEXT NOT NULL,
                question_type TEXT NOT NULL,
                is_correct INTEGER NOT NULL,
                kps_json TEXT NOT NULL,
                PRIMARY KEY (attempt_id, item_index)
            );
            CREATE INDEX IF NOT EXISTS idx_att_it_source ON attempt_items(source_question_id);

            CREATE TABLE IF NOT EXISTS study_plans (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id),
                created_at TIMESTAMP NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                total_days INTEGER NOT NULL,
                plan_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_study_plans_user ON study_plans(user_id, status);

            CREATE TABLE IF NOT EXISTS writing_grade_results (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id),
                paper_id TEXT NOT NULL,
                item_index INTEGER NOT NULL,
                user_essay TEXT NOT NULL,
                total_score REAL NOT NULL,
                content_score REAL NOT NULL,
                language_score REAL NOT NULL,
                organization_score REAL NOT NULL,
                word_count INTEGER NOT NULL,
                level TEXT NOT NULL,
                content_analysis TEXT,
                language_analysis TEXT,
                organization_analysis TEXT,
                overall_comment TEXT,
                revised_version TEXT,
                graded_at TIMESTAMP NOT NULL,
                UNIQUE(user_id, paper_id, item_index)
            );
            CREATE INDEX IF NOT EXISTS idx_writing_grade_user_paper ON writing_grade_results(user_id, paper_id);

            CREATE TABLE IF NOT EXISTS mindmaps (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id),
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                title TEXT NOT NULL,
                knowledge_point TEXT,
                outline_md TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_mindmaps_user ON mindmaps(user_id, created_at);
            """
        )
        _apply_migrations(conn)


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def create_user(username: str, password_hash: str) -> User:
    init_db()
    user = User(id=uuid4().hex, username=username, created_at=datetime.now(timezone.utc))
    with connect() as conn:
        conn.execute(
            "INSERT INTO users (id, username, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (user.id, user.username, password_hash, user.created_at.isoformat()),
        )
    return user


def _row_to_user_record(row: sqlite3.Row | None) -> UserRecord | None:
    if row is None:
        return None
    return UserRecord(
        id=row["id"],
        username=row["username"],
        password_hash=row["password_hash"],
        created_at=_dt(row["created_at"]),
        role=row["role"] if "role" in row.keys() else "user",
        status=row["status"] if "status" in row.keys() else "active",
    )


def get_user_by_username(username: str) -> UserRecord | None:
    init_db()
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    return _row_to_user_record(row)


def get_user_by_id(user_id: str) -> User | None:
    init_db()
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    record = _row_to_user_record(row)
    return User(id=record.id, username=record.username, created_at=record.created_at, role=record.role, status=record.status) if record else None


def set_user_role(user_id: str, role: str) -> None:
    init_db()
    with connect() as conn:
        conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))


def set_user_status(user_id: str, status: str) -> None:
    init_db()
    with connect() as conn:
        conn.execute("UPDATE users SET status = ? WHERE id = ?", (status, user_id))


def list_users(q: str = "", limit: int = 50, offset: int = 0) -> list[dict]:
    init_db()
    like = f"%{q}%"
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT u.id, u.username, u.created_at, u.role, u.status,
                   (SELECT COUNT(*) FROM papers p WHERE p.user_id = u.id) AS paper_count,
                   (SELECT COUNT(*) FROM attempts a WHERE a.user_id = u.id) AS attempt_count
            FROM users u
            WHERE u.username LIKE ?
            ORDER BY u.created_at DESC
            LIMIT ? OFFSET ?
            """,
            (like, limit, offset),
        ).fetchall()
    return [dict(r) for r in rows]


def count_users(q: str = "") -> int:
    init_db()
    with connect() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM users WHERE username LIKE ?", (f"%{q}%",)
        ).fetchone()[0]


def usernames_by_ids(user_ids: list[str]) -> dict[str, str]:
    """user_id → username 批量映射；查不到的 id 不在返回里。"""
    if not user_ids:
        return {}
    init_db()
    placeholders = ",".join("?" for _ in user_ids)
    with connect() as conn:
        rows = conn.execute(
            f"SELECT id, username FROM users WHERE id IN ({placeholders})",
            list(user_ids),
        ).fetchall()
    return {r["id"]: r["username"] for r in rows}


def get_user_counts(user_id: str) -> dict:
    init_db()
    with connect() as conn:
        row = conn.execute(
            """
            SELECT (SELECT COUNT(*) FROM papers p WHERE p.user_id = ?) AS paper_count,
                   (SELECT COUNT(*) FROM attempts a WHERE a.user_id = ?) AS attempt_count
            """,
            (user_id, user_id),
        ).fetchone()
    return {"paper_count": row["paper_count"], "attempt_count": row["attempt_count"]}


def admin_counts() -> dict:
    init_db()
    today = datetime.now(timezone.utc).date().isoformat()
    with connect() as conn:
        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        new_today = conn.execute(
            "SELECT COUNT(*) FROM users WHERE substr(created_at, 1, 10) = ?", (today,)
        ).fetchone()[0]
        total_papers = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
        total_attempts = conn.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]
    return {
        "total_users": total_users,
        "new_users_today": new_today,
        "total_papers": total_papers,
        "total_attempts": total_attempts,
    }


def _by_day(conn: sqlite3.Connection, table: str, ts_col: str, days: int) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = conn.execute(
        f"""
        SELECT substr({ts_col}, 1, 10) AS day, COUNT(*) AS count
        FROM {table}
        WHERE {ts_col} >= ?
        GROUP BY day
        ORDER BY day
        """,
        (since,),
    ).fetchall()
    return [{"day": r["day"], "count": r["count"]} for r in rows]


def users_created_by_day(days: int = 30) -> list[dict]:
    init_db()
    with connect() as conn:
        return _by_day(conn, "users", "created_at", days)


def papers_created_by_day(days: int = 30) -> list[dict]:
    init_db()
    with connect() as conn:
        return _by_day(conn, "papers", "generated_at", days)


def attempts_by_day(days: int = 30) -> list[dict]:
    """Per-day answered-item volume and correct rate across ALL users.

    "attempts" here counts graded attempt_items (not attempt rows), matching
    the granularity of MasteryProfile.total_attempts_considered. correct_rate
    is the daily mean of is_correct (None only when a day has no items, which
    cannot occur in a GROUP BY result)."""
    init_db()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT substr(a.answered_at, 1, 10) AS day,
                   COUNT(*) AS attempts,
                   ROUND(AVG(ai.is_correct), 4) AS correct_rate
            FROM attempts a
            JOIN attempt_items ai ON ai.attempt_id = a.id
            WHERE a.answered_at >= ?
            GROUP BY day
            ORDER BY day
            """,
            (since,),
        ).fetchall()
    return [
        {"day": r["day"], "attempts": r["attempts"], "correct_rate": r["correct_rate"]}
        for r in rows
    ]


def question_type_accuracy(window_days: int | None = None) -> list[dict]:
    """Wilson-lower-bound accuracy per question_type across ALL users.

    Uses the same _wilson_lower_bound scoring as mastery so low-sample types
    aren't over-credited. window_days None = all history."""
    init_db()
    params: list[object] = []
    where = ""
    if window_days is not None:
        since = datetime.now(timezone.utc) - timedelta(days=window_days)
        where = "WHERE a.answered_at >= ?"
        params.append(since.isoformat())
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT ai.question_type AS question_type,
                   COUNT(*) AS total,
                   SUM(ai.is_correct) AS correct
            FROM attempts a
            JOIN attempt_items ai ON ai.attempt_id = a.id
            {where}
            GROUP BY ai.question_type
            ORDER BY ai.question_type
            """,
            params,
        ).fetchall()
    return [
        {
            "question_type": r["question_type"],
            "total": r["total"],
            "accuracy": _wilson_lower_bound(r["correct"] or 0, r["total"]),
        }
        for r in rows
    ]


def update_password_hash(user_id: str, password_hash: str) -> None:
    init_db()
    with connect() as conn:
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))


def delete_sessions_by_user(user_id: str) -> None:
    init_db()
    with connect() as conn:
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))


def user_correct_rate(user_id: str) -> float | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS n, SUM(ai.is_correct) AS c
            FROM attempts a JOIN attempt_items ai ON ai.attempt_id = a.id
            WHERE a.user_id = ?
            """,
            (user_id,),
        ).fetchone()
    if not row or not row["n"]:
        return None
    return round((row["c"] or 0) / row["n"], 4)


def create_session(user_id: str, ttl_days: int = 30) -> str:
    init_db()
    now = datetime.now(timezone.utc)
    session_id = secrets.token_hex(32)
    with connect() as conn:
        conn.execute(
            "INSERT INTO sessions (session_id, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (session_id, user_id, now.isoformat(), (now + timedelta(days=ttl_days)).isoformat()),
        )
    return session_id


def get_session(session_id: str) -> Session | None:
    init_db()
    with connect() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
        if row is None:
            return None
        session = Session(
            session_id=row["session_id"],
            user_id=row["user_id"],
            created_at=_dt(row["created_at"]),
            expires_at=_dt(row["expires_at"]),
        )
        if session.expires_at < datetime.now(timezone.utc):
            conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            return None
        return session


def delete_session(session_id: str) -> None:
    init_db()
    with connect() as conn:
        conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))


def cleanup_sessions() -> int:
    init_db()
    with connect() as conn:
        cur = conn.execute("DELETE FROM sessions WHERE expires_at < ?", (datetime.now(timezone.utc).isoformat(),))
        return cur.rowcount


def slide_session(session_id: str, ttl_days: int = 30) -> None:
    init_db()
    expires_at = datetime.now(timezone.utc) + timedelta(days=ttl_days)
    with connect() as conn:
        conn.execute("UPDATE sessions SET expires_at = ? WHERE session_id = ?", (expires_at.isoformat(), session_id))


def save_paper(paper: Paper, user_id: str) -> None:
    init_db()
    with connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO papers
                (paper_id, user_id, title, generated_at, payload_json, submitted, submitted_at)
            VALUES
                (?, ?, ?, ?, ?, COALESCE((SELECT submitted FROM papers WHERE paper_id = ?), 0),
                 (SELECT submitted_at FROM papers WHERE paper_id = ?))
            """,
            (
                paper.paper_id,
                user_id,
                paper.title,
                paper.generated_at.isoformat(),
                paper.model_dump_json(),
                paper.paper_id,
                paper.paper_id,
            ),
        )


def get_paper(paper_id: str, user_id: str) -> Paper | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT payload_json FROM papers WHERE paper_id = ? AND user_id = ?",
            (paper_id, user_id),
        ).fetchone()
    return Paper.model_validate_json(row["payload_json"]) if row else None


def list_papers(user_id: str, limit: int = 100, offset: int = 0) -> list[PaperListItem]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT paper_id, title, generated_at, payload_json, submitted
            FROM papers
            WHERE user_id = ?
            ORDER BY generated_at DESC
            LIMIT ? OFFSET ?
            """,
            (user_id, limit, offset),
        ).fetchall()
    items: list[PaperListItem] = []
    for row in rows:
        payload = json.loads(row["payload_json"])
        items.append(
            PaperListItem(
                paper_id=row["paper_id"],
                title=row["title"],
                generated_at=_dt(row["generated_at"]),
                total_questions=len(payload.get("items", [])),
                submitted=bool(row["submitted"]),
            )
        )
    return items


def mark_paper_submitted(paper_id: str) -> None:
    init_db()
    with connect() as conn:
        _mark_paper_submitted(conn, paper_id)


def list_knowledge_points() -> list[KnowledgePoint]:
    with connect_bank() as conn:
        if not _table_exists(conn, "knowledge_points"):
            return []
        rows = conn.execute(
            "SELECT id, level1, level2, aliases_json FROM knowledge_points ORDER BY level1, level2"
        ).fetchall()
    return [
        KnowledgePoint(
            id=row["id"],
            level1=row["level1"],
            level2=row["level2"],
            aliases=json.loads(row["aliases_json"] or "[]"),
        )
        for row in rows
    ]


def get_question(question_id: str) -> Question | None:
    with connect_bank() as conn:
        if not _table_exists(conn, "questions"):
            return None
        row = conn.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()
        if row is None:
            return None
        return _row_to_question(conn, row)


def list_questions(
    *,
    question_type: str | None = None,
    knowledge_point_ids: list[str] | None = None,
    chapter_l2: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Question]:
    with connect_bank() as conn:
        if not _table_exists(conn, "questions"):
            return []
        clauses: list[str] = []
        params: list[object] = []
        if question_type:
            clauses.append("q.question_type = ?")
            params.append(question_type)
        if chapter_l2:
            clauses.append("q.chapter_l2 = ?")
            params.append(chapter_l2)
        joins = ""
        if knowledge_point_ids:
            joins = "JOIN question_knowledge_points qkp ON qkp.question_id = q.id"
            placeholders = ", ".join("?" for _ in knowledge_point_ids)
            clauses.append(f"qkp.knowledge_point_id IN ({placeholders})")
            params.extend(knowledge_point_ids)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = conn.execute(
            f"""
            SELECT DISTINCT q.*
            FROM questions q
            {joins}
            {where}
            ORDER BY q.id
            LIMIT ? OFFSET ?
            """,
            (*params, limit, offset),
        ).fetchall()
        return [_row_to_question(conn, row) for row in rows]


def write_question_solution(question_id: str, solution: str) -> bool:
    with connect_bank() as conn:
        if not _table_exists(conn, "questions"):
            return False
        cur = conn.execute(
            "UPDATE questions SET solution = ? WHERE id = ? AND solution IS NULL",
            (solution, question_id),
        )
        return cur.rowcount > 0


def inspect_chroma_question_collection(
    *,
    expected_question_count: int | None = None,
    chroma_path: Path | None = None,
) -> dict[str, object]:
    path = chroma_path or get_chroma_path()
    chroma_db = path / "chroma.sqlite3"
    status: dict[str, object] = {
        "path": str(path),
        "database_exists": chroma_db.is_file(),
        "collection": None,
        "dimension": None,
        "embedding_count": 0,
        "metadata_keys": [],
        "matches_question_count": False,
        "ready": False,
    }
    if not chroma_db.is_file():
        return status

    try:
        conn = sqlite3.connect(f"file:{chroma_db}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            required_tables = {"collections", "embeddings", "embedding_metadata"}
            rows = conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name IN (?, ?, ?)
                """,
                tuple(required_tables),
            ).fetchall()
            if {row["name"] for row in rows} != required_tables:
                return status

            collection = conn.execute(
                "SELECT name, dimension, schema_str FROM collections WHERE name = ?",
                (CHROMA_COLLECTION_NAME,),
            ).fetchone()
            if collection is None:
                return status

            embedding_count = int(conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0])
            metadata_keys = {
                row["key"]
                for row in conn.execute("SELECT DISTINCT key FROM embedding_metadata")
            }

            status.update(
                {
                    "collection": collection["name"],
                    "dimension": collection["dimension"],
                    "embedding_count": embedding_count,
                    "metadata_keys": sorted(metadata_keys),
                    "matches_question_count": (
                        expected_question_count is None
                        or embedding_count == expected_question_count
                    ),
                }
            )
            status["ready"] = (
                collection["name"] == CHROMA_COLLECTION_NAME
                and collection["dimension"] == 2560
                and "cosine" in (collection["schema_str"] or "")
                and CHROMA_REQUIRED_METADATA_KEYS.issubset(metadata_keys)
                and "difficulty" not in metadata_keys
                and bool(status["matches_question_count"])
                and embedding_count > 0
            )
            return status
        finally:
            conn.close()
    except sqlite3.Error:
        return status


def _row_to_question(conn: sqlite3.Connection, row: sqlite3.Row) -> Question:
    kp_rows = conn.execute(
        "SELECT knowledge_point_id FROM question_knowledge_points WHERE question_id = ? ORDER BY knowledge_point_id",
        (row["id"],),
    ).fetchall()
    options = json.loads(row["options_json"]) if row["options_json"] else None
    return Question(
        id=row["id"],
        book=row["book"],
        question_type=row["question_type"],
        chapter_l1=row["chapter_l1"],
        chapter_l2=row["chapter_l2"],
        number=row["number"],
        stem=row["stem"],
        options=[Option.model_validate(option) for option in options] if options else None,
        hint=row["hint"],
        original_sentence=row["original_sentence"],
        instruction=row["instruction"],
        template=row["template"],
        reference_expressions=row["reference_expressions"] if "reference_expressions" in row.keys() else None,
        min_words=row["min_words"] if "min_words" in row.keys() else None,
        answer=json.loads(row["answer_json"]) if row["answer_json"] else None,
        solution=row["solution"],
        knowledge_point_ids=[kp["knowledge_point_id"] for kp in kp_rows],
        source_md=row["source_md"],
        source_line=row["source_line"],
        created_at=_dt(row["created_at"]),
        version=row["version"],
    )


def get_latest_attempt(paper_id: str, user_id: str) -> dict | None:
    """Return the latest attempt for a paper as {attempt_id, items:[{index,
    is_correct, user_answer}]}, or None if the paper was never submitted.

    correct_answer is NOT stored here — the caller reconstructs it from the paper.
    """
    init_db()
    with connect() as conn:
        attempt_row = conn.execute(
            """
            SELECT id FROM attempts
            WHERE paper_id = ? AND user_id = ?
            ORDER BY answered_at DESC
            LIMIT 1
            """,
            (paper_id, user_id),
        ).fetchone()
        if not attempt_row:
            return None
        attempt_id = attempt_row["id"]
        has_user_answer = "user_answer_json" in _table_columns(conn, "attempt_items")
        cols = "item_index, is_correct" + (", user_answer_json" if has_user_answer else "")
        item_rows = conn.execute(
            f"SELECT {cols} FROM attempt_items WHERE attempt_id = ? ORDER BY item_index",
            (attempt_id,),
        ).fetchall()
    items = []
    for r in item_rows:
        raw = r["user_answer_json"] if has_user_answer else None
        items.append({
            "index": r["item_index"],
            "is_correct": bool(r["is_correct"]),
            "user_answer": json.loads(raw) if raw else None,
        })
    return {"attempt_id": attempt_id, "items": items}


def write_attempt(attempt: StoredAttempt) -> str:
    init_db()
    attempt_id = uuid4().hex
    with connect() as conn:
        _write_attempt(conn, attempt, attempt_id)
    return attempt_id


def write_attempt_and_mark_paper_submitted(attempt: StoredAttempt) -> str:
    init_db()
    attempt_id = uuid4().hex
    with connect() as conn:
        _write_attempt(conn, attempt, attempt_id)
        _mark_paper_submitted(conn, attempt.paper_id)
    return attempt_id


def _write_attempt(conn: sqlite3.Connection, attempt: StoredAttempt, attempt_id: str) -> None:
    conn.execute(
        "INSERT INTO attempts (id, user_id, paper_id, answered_at) VALUES (?, ?, ?, ?)",
        (attempt_id, attempt.user_id, attempt.paper_id, attempt.answered_at.isoformat()),
    )
    attempt_item_columns = _table_columns(conn, "attempt_items")
    if "item_index" not in attempt_item_columns:
        raise RuntimeError("attempt_items schema is missing item_index")
    for item in attempt.items:
        conn.execute(
            """
            INSERT INTO attempt_items
                (attempt_id, item_index, source_question_id, question_type, is_correct, kps_json, user_answer_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                attempt_id,
                item.index,
                item.source_question_id,
                item.question_type,
                1 if item.is_correct else 0,
                json.dumps(item.knowledge_point_ids, ensure_ascii=False),
                json.dumps(item.user_answer, ensure_ascii=False) if item.user_answer is not None else None,
            ),
        )


def _mark_paper_submitted(conn: sqlite3.Connection, paper_id: str) -> None:
    conn.execute(
        "UPDATE papers SET submitted = 1, submitted_at = ? WHERE paper_id = ?",
        (datetime.now(timezone.utc).isoformat(), paper_id),
    )


def save_writing_grade_results(user_id: str, paper_id: str, items: list[dict]) -> None:
    """Persist essay + writing grade results keyed by (user_id, paper_id, item_index).

    items: list of {
        index: int, user_essay: str,
        total_score, content_score, language_score, organization_score,
        word_count, level,
        content_analysis, language_analysis, organization_analysis, overall_comment, revised_version
    }
    """
    init_db()
    now = datetime.now(timezone.utc).isoformat()
    with connect() as conn:
        for it in items:
            row_id = uuid4().hex
            conn.execute(
                """
                INSERT INTO writing_grade_results
                    (id, user_id, paper_id, item_index, user_essay, total_score,
                     content_score, language_score, organization_score, word_count, level,
                     content_analysis, language_analysis, organization_analysis, overall_comment,
                     revised_version, graded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, paper_id, item_index) DO UPDATE SET
                    user_essay = excluded.user_essay,
                    total_score = excluded.total_score,
                    content_score = excluded.content_score,
                    language_score = excluded.language_score,
                    organization_score = excluded.organization_score,
                    word_count = excluded.word_count,
                    level = excluded.level,
                    content_analysis = excluded.content_analysis,
                    language_analysis = excluded.language_analysis,
                    organization_analysis = excluded.organization_analysis,
                    overall_comment = excluded.overall_comment,
                    revised_version = excluded.revised_version,
                    graded_at = excluded.graded_at
                """,
                (
                    row_id, user_id, paper_id, it["index"], it["user_essay"],
                    float(it["total_score"]), float(it["content_score"]),
                    float(it["language_score"]), float(it["organization_score"]),
                    int(it["word_count"]), it["level"],
                    it.get("content_analysis"), it.get("language_analysis"),
                    it.get("organization_analysis"), it.get("overall_comment"),
                    it.get("revised_version"), now,
                ),
            )


def get_writing_grade_results(paper_id: str, user_id: str) -> list[dict]:
    """Return the latest stored writing grade results for a paper."""
    init_db()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT item_index, user_essay, total_score, content_score, language_score,
                   organization_score, word_count, level, content_analysis, language_analysis,
                   organization_analysis, overall_comment, revised_version, graded_at
            FROM writing_grade_results
            WHERE paper_id = ? AND user_id = ?
            ORDER BY item_index
            """,
            (paper_id, user_id),
        ).fetchall()
    return [dict(r) for r in rows]


def mark_paper_submitted_if_needed(paper_id: str, user_id: str) -> None:
    """Mark a paper submitted if it is not already, so list view shows "已提交".

    This is used when only the writing endpoint submitted a new attempt (no
    objective POST /attempts call was made).
    """
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT submitted FROM papers WHERE paper_id = ? AND user_id = ?",
            (paper_id, user_id),
        ).fetchone()
        if not row or bool(row["submitted"]):
            return
        conn.execute(
            "UPDATE papers SET submitted = 1, submitted_at = ? WHERE paper_id = ?",
            (datetime.now(timezone.utc).isoformat(), paper_id),
        )


def save_writing_attempt_items(user_id: str, paper_id: str, items: list[dict]) -> str | None:
    """Insert or upsert essay user_answer into the latest attempt for this paper so that
    AnswerCard / review replay show the writing item as answered.

    If no attempt record exists yet (paper has only writing items and no objective
    submission via POST /attempts), create a synthetic attempt record so that
    attempt_items can be attached and the list-views reflect submission status.

    Returns the attempt_id if we wrote to an attempt, or None on failure.
    """
    init_db()
    with connect() as conn:
        attempt_row = conn.execute(
            """
            SELECT id FROM attempts
            WHERE paper_id = ? AND user_id = ?
            ORDER BY answered_at DESC LIMIT 1
            """,
            (paper_id, user_id),
        ).fetchone()
        if not attempt_row:
            # No attempt yet — create one so attempt_items rows can be linked.
            attempt_id = uuid4().hex
            now = datetime.now(timezone.utc).isoformat()
            try:
                conn.execute(
                    """
                    INSERT INTO attempts (id, paper_id, user_id, answered_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (attempt_id, paper_id, user_id, now),
                )
            except Exception:
                return None
        else:
            attempt_id = attempt_row["id"]
        for it in items:
            conn.execute(
                """
                INSERT INTO attempt_items
                    (attempt_id, item_index, source_question_id, question_type, is_correct,
                     kps_json, user_answer_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(attempt_id, item_index) DO UPDATE SET
                    user_answer_json = excluded.user_answer_json,
                    is_correct = excluded.is_correct,
                    kps_json = excluded.kps_json,
                    source_question_id = excluded.source_question_id,
                    question_type = excluded.question_type
                """,
                (
                    attempt_id,
                    it["index"],
                    it["source_question_id"],
                    "writing",
                    0,
                    json.dumps(it.get("knowledge_point_ids") or [], ensure_ascii=False),
                    json.dumps(it["user_essay"], ensure_ascii=False),
                ),
            )
        return attempt_id


def _migrate_users_role(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "users"):
        return
    if "role" in _table_columns(conn, "users"):
        return
    conn.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")


def _migrate_users_status(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "users"):
        return
    if "status" in _table_columns(conn, "users"):
        return
    conn.execute("ALTER TABLE users ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")


def _migrate_attempt_items_item_index(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "attempt_items"):
        return
    columns = _table_columns(conn, "attempt_items")
    if "item_index" in columns:
        return
    legacy_rows = conn.execute(
        """
        SELECT attempt_id, source_question_id, question_type, is_correct, kps_json
        FROM attempt_items
        ORDER BY attempt_id, source_question_id
        """
    ).fetchall()
    conn.execute("ALTER TABLE attempt_items RENAME TO attempt_items_legacy")
    conn.execute(
        """
        CREATE TABLE attempt_items (
            attempt_id TEXT NOT NULL REFERENCES attempts(id),
            item_index INTEGER NOT NULL,
            source_question_id TEXT NOT NULL,
            question_type TEXT NOT NULL,
            is_correct INTEGER NOT NULL,
            kps_json TEXT NOT NULL,
            PRIMARY KEY (attempt_id, item_index)
        )
        """
    )
    per_attempt_counts: dict[str, int] = defaultdict(int)
    for row in legacy_rows:
        per_attempt_counts[row["attempt_id"]] += 1
        conn.execute(
            """
            INSERT INTO attempt_items
                (attempt_id, item_index, source_question_id, question_type, is_correct, kps_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                row["attempt_id"],
                per_attempt_counts[row["attempt_id"]],
                row["source_question_id"],
                row["question_type"],
                row["is_correct"],
                row["kps_json"],
            ),
        )
    conn.execute("DROP TABLE attempt_items_legacy")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_att_it_source ON attempt_items(source_question_id)")


def _migrate_attempt_items_user_answer(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "attempt_items"):
        return
    if "user_answer_json" in _table_columns(conn, "attempt_items"):
        return
    conn.execute("ALTER TABLE attempt_items ADD COLUMN user_answer_json TEXT")


def _migrate_writing_grade_results(conn: sqlite3.Connection) -> None:
    if _table_exists(conn, "writing_grade_results"):
        return
    conn.execute(
        """
        CREATE TABLE writing_grade_results (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id),
            paper_id TEXT NOT NULL,
            item_index INTEGER NOT NULL,
            user_essay TEXT NOT NULL,
            total_score REAL NOT NULL,
            content_score REAL NOT NULL,
            language_score REAL NOT NULL,
            organization_score REAL NOT NULL,
            word_count INTEGER NOT NULL,
            level TEXT NOT NULL,
            content_analysis TEXT,
            language_analysis TEXT,
            organization_analysis TEXT,
            overall_comment TEXT,
            revised_version TEXT,
            graded_at TIMESTAMP NOT NULL,
            UNIQUE(user_id, paper_id, item_index)
        );
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_writing_grade_user_paper ON writing_grade_results(user_id, paper_id)",
    )


def _migrate_mindmaps(conn: sqlite3.Connection) -> None:
    if _table_exists(conn, "mindmaps"):
        return
    conn.execute(
        """
        CREATE TABLE mindmaps (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id),
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL,
            title TEXT NOT NULL,
            knowledge_point TEXT,
            outline_md TEXT NOT NULL
        );
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_mindmaps_user ON mindmaps(user_id, created_at)",
    )


def _migrate_vocabulary_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS vocabulary_wordlists (
            id TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            source_url TEXT NOT NULL,
            source_accessed_at TEXT NOT NULL,
            source_sha256 TEXT NOT NULL,
            imported_at TIMESTAMP NOT NULL
        );

        CREATE TABLE IF NOT EXISTS vocabulary_words (
            id TEXT PRIMARY KEY,
            wordlist_id TEXT NOT NULL REFERENCES vocabulary_wordlists(id),
            term TEXT NOT NULL,
            normalized_term TEXT NOT NULL UNIQUE,
            part_of_speech TEXT NOT NULL,
            meanings_json TEXT NOT NULL,
            example_en TEXT NOT NULL,
            example_zh TEXT NOT NULL,
            source_category TEXT NOT NULL DEFAULT 'shanghai_extension'
                CHECK(source_category IN ('national_core', 'shanghai_extension')),
            is_active INTEGER NOT NULL DEFAULT 1
        );
        CREATE INDEX IF NOT EXISTS idx_vocabulary_words_active ON vocabulary_words(is_active, source_category, id);

        CREATE TABLE IF NOT EXISTS vocabulary_settings (
            user_id TEXT PRIMARY KEY REFERENCES users(id),
            daily_new_limit INTEGER NOT NULL DEFAULT 20 CHECK(daily_new_limit BETWEEN 10 AND 50)
        );

        CREATE TABLE IF NOT EXISTS vocabulary_progress (
            user_id TEXT NOT NULL REFERENCES users(id),
            word_id TEXT NOT NULL REFERENCES vocabulary_words(id),
            stage INTEGER NOT NULL DEFAULT 0 CHECK(stage BETWEEN 0 AND 5),
            introduced_at TIMESTAMP NOT NULL,
            last_reviewed_at TIMESTAMP NOT NULL,
            due_at TIMESTAMP NOT NULL,
            review_count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(user_id, word_id)
        );
        CREATE INDEX IF NOT EXISTS idx_vocabulary_progress_due ON vocabulary_progress(user_id, due_at);

        CREATE TABLE IF NOT EXISTS vocabulary_daily_cards (
            user_id TEXT NOT NULL REFERENCES users(id),
            study_date TEXT NOT NULL,
            word_id TEXT NOT NULL REFERENCES vocabulary_words(id),
            card_type TEXT NOT NULL CHECK(card_type IN ('review', 'new')),
            completed_at TIMESTAMP,
            PRIMARY KEY(user_id, study_date, word_id)
        );
        CREATE INDEX IF NOT EXISTS idx_vocabulary_cards_open ON vocabulary_daily_cards(user_id, study_date, completed_at);

        CREATE TABLE IF NOT EXISTS vocabulary_review_logs (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id),
            word_id TEXT NOT NULL REFERENCES vocabulary_words(id),
            reviewed_at TIMESTAMP NOT NULL,
            spelling_correct INTEGER NOT NULL,
            requested_rating TEXT NOT NULL CHECK(requested_rating IN ('known', 'fuzzy', 'forgot')),
            applied_rating TEXT NOT NULL CHECK(applied_rating IN ('known', 'fuzzy', 'forgot')),
            stage_after INTEGER NOT NULL,
            next_due_at TIMESTAMP NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_vocabulary_logs_user_time ON vocabulary_review_logs(user_id, reviewed_at);
        """
    )


def _migrate_vocabulary_retry_queue(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS vocabulary_daily_retry_queue (
            user_id TEXT NOT NULL REFERENCES users(id),
            study_date TEXT NOT NULL,
            word_id TEXT NOT NULL REFERENCES vocabulary_words(id),
            first_rating TEXT NOT NULL CHECK(first_rating IN ('fuzzy', 'forgot')),
            last_rating TEXT NOT NULL CHECK(last_rating IN ('known', 'fuzzy', 'forgot')),
            retry_count INTEGER NOT NULL DEFAULT 0,
            queue_order INTEGER NOT NULL,
            passed_at TIMESTAMP,
            PRIMARY KEY(user_id, study_date, word_id)
        );
        CREATE INDEX IF NOT EXISTS idx_vocabulary_retry_open
            ON vocabulary_daily_retry_queue(user_id, study_date, passed_at, queue_order);
        """
    )


def _migrate_vocabulary_word_sources(conn: sqlite3.Connection) -> None:
    """Add provenance for the merged national-core / Shanghai-extension list."""
    if _table_exists(conn, "vocabulary_words") and "source_category" not in _table_columns(conn, "vocabulary_words"):
        conn.execute(
            "ALTER TABLE vocabulary_words ADD COLUMN source_category TEXT NOT NULL DEFAULT 'shanghai_extension'"
        )
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS vocabulary_wordlist_sources (
            wordlist_id TEXT NOT NULL REFERENCES vocabulary_wordlists(id),
            category TEXT NOT NULL CHECK(category IN ('national_core', 'shanghai_extension')),
            label TEXT NOT NULL,
            source_url TEXT NOT NULL,
            source_accessed_at TEXT NOT NULL,
            source_sha256 TEXT NOT NULL,
            PRIMARY KEY(wordlist_id, category)
        );
        CREATE INDEX IF NOT EXISTS idx_vocabulary_wordlist_sources_list
            ON vocabulary_wordlist_sources(wordlist_id, category);
        CREATE INDEX IF NOT EXISTS idx_vocabulary_words_category
            ON vocabulary_words(is_active, source_category, id);
        """
    )


def _ensure_schema_migrations(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id TEXT PRIMARY KEY,
            applied_at TIMESTAMP NOT NULL
        )
        """
    )


def _apply_migrations(conn: sqlite3.Connection) -> None:
    migrations = [
        (MIGRATION_ATTEMPT_ITEMS_ITEM_INDEX, _migrate_attempt_items_item_index),
        (MIGRATION_VOCABULARY_SCHEMA, _migrate_vocabulary_schema),
        (MIGRATION_VOCABULARY_RETRY_QUEUE, _migrate_vocabulary_retry_queue),
        (MIGRATION_VOCABULARY_WORD_SOURCES, _migrate_vocabulary_word_sources),
        (MIGRATION_USERS_ROLE, _migrate_users_role),
        (MIGRATION_USERS_STATUS, _migrate_users_status),
        (MIGRATION_ATTEMPT_ITEMS_USER_ANSWER, _migrate_attempt_items_user_answer),
        (MIGRATION_WRITING_GRADE_RESULTS, _migrate_writing_grade_results),
        (MIGRATION_MINDMAPS, _migrate_mindmaps),
    ]
    for migration_id, migration in migrations:
        if _migration_applied(conn, migration_id):
            continue
        migration(conn)
        conn.execute(
            "INSERT INTO schema_migrations (id, applied_at) VALUES (?, ?)",
            (migration_id, datetime.now(timezone.utc).isoformat()),
        )


def _migration_applied(conn: sqlite3.Connection, migration_id: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM schema_migrations WHERE id = ?",
            (migration_id,),
        ).fetchone()
        is not None
    )


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone() is not None


def build_mastery_profile(user_id: str, window_days: int | None = None) -> MasteryProfile:
    init_db()
    params: list[object] = [user_id]
    where = "a.user_id = ?"
    if window_days is not None:
        since = datetime.now(timezone.utc) - timedelta(days=window_days)
        where += " AND a.answered_at >= ?"
        params.append(since.isoformat())
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT ai.kps_json, ai.question_type, ai.is_correct
            FROM attempts a
            JOIN attempt_items ai ON ai.attempt_id = a.id
            WHERE {where}
            """,
            params,
        ).fetchall()
    kp_totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    wrong_types: Counter[str] = Counter()
    for row in rows:
        is_correct = bool(row["is_correct"])
        for kp in json.loads(row["kps_json"]):
            kp_totals[kp][0] += 1
            kp_totals[kp][1] += 1 if is_correct else 0
        if not is_correct:
            wrong_types[row["question_type"]] += 1
    weak_kps = [
        KPMastery(
            knowledge_point_id=kp,
            attempts=attempts,
            mastery=_wilson_lower_bound(correct, attempts),
        )
        for kp, (attempts, correct) in kp_totals.items()
    ]
    weak_kps.sort(key=lambda item: item.mastery)
    return MasteryProfile(
        user_id=user_id,
        window_days=window_days,
        weak_kps=weak_kps[:8],
        dominant_types=[item[0] for item in wrong_types.most_common(3)],
        total_attempts_considered=len(rows),
    )


def _wilson_lower_bound(correct: int, total: int, z: float = 1.96) -> float:
    if total == 0:
        return 0.0
    phat = correct / total
    denom = 1 + z * z / total
    centre = phat + z * z / (2 * total)
    margin = z * math.sqrt((phat * (1 - phat) + z * z / (4 * total)) / total)
    return max(0.0, (centre - margin) / denom)


# ─── Study Plans ───────────────────────────────────────────────────────────

def save_study_plan(user_id: str, total_days: int, plan_data: dict) -> str:
    """Persist a new study plan, superseding any existing active plan for the user."""
    init_db()
    plan_id = uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    with connect() as conn:
        conn.execute(
            "UPDATE study_plans SET status = 'superseded' WHERE user_id = ? AND status = 'active'",
            (user_id,),
        )
        conn.execute(
            "INSERT INTO study_plans (id, user_id, created_at, status, total_days, plan_json) VALUES (?, ?, ?, 'active', ?, ?)",
            (plan_id, user_id, now, total_days, json.dumps(plan_data, ensure_ascii=False)),
        )
    return plan_id


def get_latest_study_plan(user_id: str) -> dict | None:
    """Return the most recently created active study plan for the user, or None."""
    init_db()
    with connect() as conn:
        if not _table_exists(conn, "study_plans"):
            return None
        row = conn.execute(
            "SELECT plan_json FROM study_plans WHERE user_id = ? AND status = 'active' ORDER BY created_at DESC LIMIT 1",
            (user_id,),
        ).fetchone()
    return json.loads(row["plan_json"]) if row else None


# ─── Vocabulary ─────────────────────────────────────────────────────────────

def _vocabulary_now() -> datetime:
    return datetime.now(timezone.utc)


def _vocabulary_date(now: datetime | None = None) -> str:
    return (now or _vocabulary_now()).astimezone(VOCABULARY_TIMEZONE).date().isoformat()


def _normalize_vocabulary_term(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def _normalize_vocabulary_meaning(value: str) -> str:
    """Keep separators between senses, but remove source punctuation at the end."""
    import re

    return re.sub(r"[\uFF1B;\s]+$", "", value.strip()).strip()


def seed_vocabulary_from_json(path: str | Path, *, expected_count: int | None = None) -> int:
    """Upsert a versioned word list without touching any learner progress."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    metadata = payload.get("metadata")
    words = payload.get("words")
    if not isinstance(metadata, dict) or not isinstance(words, list):
        raise ValueError("vocabulary file must contain metadata and words")
    required_metadata = {"id", "label", "source_url", "source_accessed_at", "source_sha256"}
    if not required_metadata.issubset(metadata):
        raise ValueError("vocabulary metadata is incomplete")
    declared_count = metadata.get("expected_count")
    if declared_count is not None and (not isinstance(declared_count, int) or declared_count != len(words)):
        raise ValueError("vocabulary metadata expected_count does not match entries")
    if expected_count is not None and len(words) != expected_count:
        raise ValueError(f"expected {expected_count} vocabulary entries, got {len(words)}")

    sources = metadata.get("sources")
    if sources is None:
        sources = [{
            "category": "shanghai_extension",
            "label": metadata["label"],
            "source_url": metadata["source_url"],
            "source_accessed_at": metadata["source_accessed_at"],
            "source_sha256": metadata["source_sha256"],
        }]
    if not isinstance(sources, list) or not sources:
        raise ValueError("vocabulary metadata sources must be a non-empty list")
    prepared_sources: list[tuple[str, str, str, str, str]] = []
    source_categories: set[str] = set()
    valid_categories = {"national_core", "shanghai_extension"}
    for source in sources:
        if not isinstance(source, dict):
            raise ValueError("vocabulary source entries must be objects")
        category = str(source.get("category", "")).strip()
        values = tuple(str(source.get(field, "")).strip() for field in ("label", "source_url", "source_accessed_at", "source_sha256"))
        if category not in valid_categories or not all(values) or category in source_categories:
            raise ValueError("vocabulary source metadata is incomplete or duplicated")
        source_categories.add(category)
        prepared_sources.append((category, *values))

    ids: set[str] = set()
    normalized_terms: set[str] = set()
    prepared: list[tuple[str, str, str, str, list[str], str, str, str]] = []
    for item in words:
        if not isinstance(item, dict):
            raise ValueError("vocabulary entries must be objects")
        try:
            word_id = str(item["id"])
            term = str(item["term"]).strip()
            pos = str(item["part_of_speech"]).strip()
            meanings = item["meanings"]
            example_en = str(item["example_en"]).strip()
            example_zh = str(item["example_zh"]).strip()
            source_category = str(item.get("source_category", "shanghai_extension")).strip()
        except KeyError as exc:
            raise ValueError(f"vocabulary entry is missing {exc.args[0]}") from exc
        normalized = _normalize_vocabulary_term(term)
        if not word_id or not term or not pos or not isinstance(meanings, list) or not meanings or not example_en or not example_zh:
            raise ValueError(f"vocabulary entry {word_id or '<unknown>'} is incomplete")
        if source_category not in source_categories:
            raise ValueError(f"vocabulary entry {word_id or term} has an unknown source category")
        if word_id in ids or normalized in normalized_terms:
            raise ValueError(f"duplicate vocabulary entry {word_id or term}")
        ids.add(word_id)
        normalized_terms.add(normalized)
        cleaned_meanings = [_normalize_vocabulary_meaning(str(value)) for value in meanings]
        if not all(cleaned_meanings):
            raise ValueError(f"vocabulary entry {word_id or term} has an empty meaning")
        prepared.append((word_id, term, normalized, pos, cleaned_meanings, example_en, example_zh, source_category))

    init_db()
    now = _vocabulary_now().isoformat()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO vocabulary_wordlists (id, label, source_url, source_accessed_at, source_sha256, imported_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                label = excluded.label,
                source_url = excluded.source_url,
                source_accessed_at = excluded.source_accessed_at,
                source_sha256 = excluded.source_sha256,
                imported_at = excluded.imported_at
            """,
            (metadata["id"], metadata["label"], metadata["source_url"], metadata["source_accessed_at"], metadata["source_sha256"], now),
        )
        for category, label, source_url, source_accessed_at, source_sha256 in prepared_sources:
            conn.execute(
                """
                INSERT INTO vocabulary_wordlist_sources
                    (wordlist_id, category, label, source_url, source_accessed_at, source_sha256)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(wordlist_id, category) DO UPDATE SET
                    label = excluded.label,
                    source_url = excluded.source_url,
                    source_accessed_at = excluded.source_accessed_at,
                    source_sha256 = excluded.source_sha256
                """,
                (metadata["id"], category, label, source_url, source_accessed_at, source_sha256),
            )
        for word_id, term, normalized, pos, meanings, example_en, example_zh, source_category in prepared:
            conn.execute(
                """
                INSERT INTO vocabulary_words
                    (id, wordlist_id, term, normalized_term, part_of_speech, meanings_json, example_en, example_zh, source_category, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(id) DO UPDATE SET
                    wordlist_id = excluded.wordlist_id,
                    term = excluded.term,
                    normalized_term = excluded.normalized_term,
                    part_of_speech = excluded.part_of_speech,
                    meanings_json = excluded.meanings_json,
                    example_en = excluded.example_en,
                    example_zh = excluded.example_zh,
                    source_category = excluded.source_category,
                    is_active = 1
                """,
                (word_id, metadata["id"], term, normalized, pos, json.dumps(meanings, ensure_ascii=False), example_en, example_zh, source_category),
            )
    return len(prepared)


def _vocabulary_settings(conn: sqlite3.Connection, user_id: str) -> int:
    conn.execute(
        "INSERT OR IGNORE INTO vocabulary_settings (user_id, daily_new_limit) VALUES (?, ?)",
        (user_id, DEFAULT_DAILY_NEW_LIMIT),
    )
    return int(conn.execute("SELECT daily_new_limit FROM vocabulary_settings WHERE user_id = ?", (user_id,)).fetchone()[0])


def _mask_vocabulary_example(example: str, term: str) -> str:
    import re

    if not term:
        return example
    return re.sub(re.escape(term), "_____", example, flags=re.IGNORECASE)


def _ensure_vocabulary_daily_cards(conn: sqlite3.Connection, user_id: str, now: datetime) -> int:
    study_date = _vocabulary_date(now)
    existing = conn.execute(
        "SELECT COUNT(*) FROM vocabulary_daily_cards WHERE user_id = ? AND study_date = ?",
        (user_id, study_date),
    ).fetchone()[0]
    if not existing:
        due_rows = conn.execute(
            """
            SELECT word_id FROM vocabulary_progress
            WHERE user_id = ? AND due_at <= ?
            ORDER BY due_at, word_id
            """,
            (user_id, now.isoformat()),
        ).fetchall()
        for row in due_rows:
            conn.execute(
                "INSERT INTO vocabulary_daily_cards (user_id, study_date, word_id, card_type) VALUES (?, ?, ?, 'review')",
                (user_id, study_date, row["word_id"]),
            )
    return _append_vocabulary_daily_new_cards(conn, user_id, study_date, _vocabulary_settings(conn, user_id))


def _append_vocabulary_daily_new_cards(
    conn: sqlite3.Connection, user_id: str, study_date: str, daily_new_limit: int
) -> int:
    """Fill today's new-word allocation without changing cards already issued."""
    issued_count = int(conn.execute(
        """
        SELECT COUNT(*) FROM vocabulary_daily_cards
        WHERE user_id = ? AND study_date = ? AND card_type = 'new'
        """,
        (user_id, study_date),
    ).fetchone()[0])
    additional = max(daily_new_limit - issued_count, 0)
    if additional == 0:
        return 0
    new_rows = conn.execute(
        """
        SELECT w.id FROM vocabulary_words w
        LEFT JOIN vocabulary_progress p ON p.word_id = w.id AND p.user_id = ?
        WHERE w.is_active = 1 AND p.word_id IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM vocabulary_daily_cards c
              WHERE c.user_id = ? AND c.study_date = ? AND c.word_id = w.id
          )
        ORDER BY CASE w.source_category WHEN 'national_core' THEN 0 ELSE 1 END, w.id
        LIMIT ?
        """,
        (user_id, user_id, study_date, additional),
    ).fetchall()
    for row in new_rows:
        conn.execute(
            "INSERT INTO vocabulary_daily_cards (user_id, study_date, word_id, card_type) VALUES (?, ?, ?, 'new')",
            (user_id, study_date, row["id"]),
        )
    return len(new_rows)


def _vocabulary_counts(conn: sqlite3.Connection, user_id: str, study_date: str) -> dict:
    rows = conn.execute(
        """
        SELECT card_type, COUNT(*) AS count,
               SUM(CASE WHEN completed_at IS NOT NULL THEN 1 ELSE 0 END) AS completed
        FROM vocabulary_daily_cards
        WHERE user_id = ? AND study_date = ?
        GROUP BY card_type
        """,
        (user_id, study_date),
    ).fetchall()
    card_counts = {row["card_type"]: (int(row["count"]), int(row["completed"] or 0)) for row in rows}
    retry = conn.execute(
        """
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN passed_at IS NOT NULL THEN 1 ELSE 0 END) AS completed
        FROM vocabulary_daily_retry_queue WHERE user_id = ? AND study_date = ?
        """,
        (user_id, study_date),
    ).fetchone()
    review_total, review_completed = card_counts.get("review", (0, 0))
    new_total, new_completed = card_counts.get("new", (0, 0))
    retry_total = int(retry["total"] or 0)
    retry_completed = int(retry["completed"] or 0)
    retry_pending = retry_total - retry_completed
    return {
        "scheduled_review_total": review_total,
        "scheduled_review_completed": review_completed,
        "new_total": new_total,
        "new_completed": new_completed,
        "retry_total": retry_total,
        "retry_completed": retry_completed,
        "retry_pending": retry_pending,
        "remaining_count": review_total - review_completed + new_total - new_completed + retry_pending,
    }


def _vocabulary_active_card(conn: sqlite3.Connection, user_id: str, study_date: str) -> dict | None:
    initial = conn.execute(
        """
        SELECT c.word_id, c.card_type, w.term
        FROM vocabulary_daily_cards c JOIN vocabulary_words w ON w.id = c.word_id
        WHERE c.user_id = ? AND c.study_date = ? AND c.completed_at IS NULL
        ORDER BY CASE c.card_type WHEN 'review' THEN 0 ELSE 1 END, c.word_id
        LIMIT 1
        """,
        (user_id, study_date),
    ).fetchone()
    if initial:
        return {
            "word_id": initial["word_id"],
            "term": initial["term"],
            "origin": "scheduled_review" if initial["card_type"] == "review" else "new",
            "phase": "scheduled_review" if initial["card_type"] == "review" else "new",
            "retry_count": 0,
        }
    retry = conn.execute(
        """
        SELECT q.word_id, q.retry_count, w.term, c.card_type
        FROM vocabulary_daily_retry_queue q
        JOIN vocabulary_words w ON w.id = q.word_id
        JOIN vocabulary_daily_cards c ON c.user_id = q.user_id AND c.study_date = q.study_date AND c.word_id = q.word_id
        WHERE q.user_id = ? AND q.study_date = ? AND q.passed_at IS NULL
        ORDER BY q.queue_order, q.word_id
        LIMIT 1
        """,
        (user_id, study_date),
    ).fetchone()
    if retry:
        return {
            "word_id": retry["word_id"],
            "term": retry["term"],
            "origin": "scheduled_review" if retry["card_type"] == "review" else "new",
            "phase": "same_day_retry",
            "retry_count": int(retry["retry_count"]),
        }
    return None


def _vocabulary_next_queue_order(conn: sqlite3.Connection, user_id: str, study_date: str) -> int:
    return int(conn.execute(
        "SELECT COALESCE(MAX(queue_order), 0) + 1 FROM vocabulary_daily_retry_queue WHERE user_id = ? AND study_date = ?",
        (user_id, study_date),
    ).fetchone()[0])


def _update_vocabulary_progress(
    conn: sqlite3.Connection,
    user_id: str,
    word_id: str,
    rating: Literal["known", "fuzzy", "forgot"],
    now: datetime,
) -> tuple[int, datetime]:
    progress = conn.execute(
        "SELECT stage, introduced_at, review_count FROM vocabulary_progress WHERE user_id = ? AND word_id = ?",
        (user_id, word_id),
    ).fetchone()
    current_stage = int(progress["stage"]) if progress else 0
    if rating == "known":
        stage = min(current_stage + 1, len(VOCABULARY_INTERVALS))
        delay_days = VOCABULARY_INTERVALS[stage - 1]
    elif rating == "fuzzy":
        stage = current_stage
        delay_days = 1
    else:
        stage = 0
        delay_days = 1
    next_due_at = now + timedelta(days=delay_days)
    introduced_at = progress["introduced_at"] if progress else now.isoformat()
    review_count = int(progress["review_count"]) + 1 if progress else 1
    conn.execute(
        """
        INSERT INTO vocabulary_progress (user_id, word_id, stage, introduced_at, last_reviewed_at, due_at, review_count)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, word_id) DO UPDATE SET
            stage = excluded.stage, last_reviewed_at = excluded.last_reviewed_at,
            due_at = excluded.due_at, review_count = excluded.review_count
        """,
        (user_id, word_id, stage, introduced_at, now.isoformat(), next_due_at.isoformat(), review_count),
    )
    conn.execute(
        """
        INSERT INTO vocabulary_review_logs
            (id, user_id, word_id, reviewed_at, spelling_correct, requested_rating, applied_rating, stage_after, next_due_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (uuid4().hex, user_id, word_id, now.isoformat(), int(rating == "known"), rating, rating, stage, next_due_at.isoformat()),
    )
    return stage, next_due_at


def get_vocabulary_today(user_id: str, now: datetime | None = None) -> dict:
    init_db()
    now = now or _vocabulary_now()
    study_date = _vocabulary_date(now)
    with connect() as conn:
        _ensure_vocabulary_daily_cards(conn, user_id, now)
        limit = _vocabulary_settings(conn, user_id)
        active = _vocabulary_active_card(conn, user_id, study_date)
        counts = _vocabulary_counts(conn, user_id, study_date)
    return {
        "date": study_date,
        "daily_new_limit": limit,
        "phase": active["phase"] if active else "completed",
        "current_card": {
            "word_id": active["word_id"], "term": active["term"], "origin": active["origin"], "retry_count": active["retry_count"],
        } if active else None,
        "counts": counts,
    }


def judge_vocabulary_card(
    user_id: str,
    word_id: str,
    rating: Literal["known", "fuzzy", "forgot"],
    now: datetime | None = None,
) -> dict:
    init_db()
    now = now or _vocabulary_now()
    study_date = _vocabulary_date(now)
    with connect() as conn:
        _ensure_vocabulary_daily_cards(conn, user_id, now)
        active = _vocabulary_active_card(conn, user_id, study_date)
        if active is None or active["word_id"] != word_id:
            raise ValueError("word is not the current vocabulary card")
        detail = conn.execute(
            "SELECT term, part_of_speech, meanings_json, example_en, example_zh FROM vocabulary_words WHERE id = ?",
            (word_id,),
        ).fetchone()
        if detail is None:
            raise ValueError("vocabulary word not found")
        stage, next_due_at = _update_vocabulary_progress(conn, user_id, word_id, rating, now)
        if active["phase"] == "same_day_retry":
            if rating == "known":
                conn.execute(
                    "UPDATE vocabulary_daily_retry_queue SET last_rating = ?, passed_at = ? WHERE user_id = ? AND study_date = ? AND word_id = ?",
                    (rating, now.isoformat(), user_id, study_date, word_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE vocabulary_daily_retry_queue
                    SET last_rating = ?, retry_count = retry_count + 1, queue_order = ?
                    WHERE user_id = ? AND study_date = ? AND word_id = ?
                    """,
                    (rating, _vocabulary_next_queue_order(conn, user_id, study_date), user_id, study_date, word_id),
                )
        else:
            conn.execute(
                "UPDATE vocabulary_daily_cards SET completed_at = ? WHERE user_id = ? AND study_date = ? AND word_id = ?",
                (now.isoformat(), user_id, study_date, word_id),
            )
            if rating != "known":
                conn.execute(
                    """
                    INSERT INTO vocabulary_daily_retry_queue
                        (user_id, study_date, word_id, first_rating, last_rating, retry_count, queue_order)
                    VALUES (?, ?, ?, ?, ?, 0, ?)
                    """,
                    (user_id, study_date, word_id, rating, rating, _vocabulary_next_queue_order(conn, user_id, study_date)),
                )
        next_active = _vocabulary_active_card(conn, user_id, study_date)
        counts = _vocabulary_counts(conn, user_id, study_date)
    return {
        "word_id": word_id,
        "rating": rating,
        "detail": {
            "word_id": word_id, "term": detail["term"], "part_of_speech": detail["part_of_speech"],
            "meanings": json.loads(detail["meanings_json"]), "example_en": detail["example_en"], "example_zh": detail["example_zh"],
        },
        "next_due_at": next_due_at,
        "stage": stage,
        "added_to_same_day_retry": rating != "known",
        "phase": next_active["phase"] if next_active else "completed",
        "counts": counts,
    }


def get_vocabulary_progress(user_id: str, now: datetime | None = None) -> dict:
    init_db()
    now = now or _vocabulary_now()
    study_date = _vocabulary_date(now)
    with connect() as conn:
        _ensure_vocabulary_daily_cards(conn, user_id, now)
        limit = _vocabulary_settings(conn, user_id)
        task_counts = _vocabulary_counts(conn, user_id, study_date)
        due_count = int(conn.execute(
            "SELECT COUNT(*) FROM vocabulary_progress WHERE user_id = ? AND due_at <= ?",
            (user_id, now.isoformat()),
        ).fetchone()[0])
        learned_count = int(conn.execute(
            """
            SELECT COUNT(*) FROM vocabulary_progress p
            JOIN vocabulary_words w ON w.id = p.word_id
            WHERE p.user_id = ? AND p.stage >= 1 AND w.is_active = 1
            """,
            (user_id,),
        ).fetchone()[0])
        mastered_count = int(conn.execute(
            """
            SELECT COUNT(*) FROM vocabulary_progress p
            JOIN vocabulary_words w ON w.id = p.word_id
            WHERE p.user_id = ? AND p.stage = ? AND w.is_active = 1
            """,
            (user_id, len(VOCABULARY_INTERVALS)),
        ).fetchone()[0])
        total_words = int(conn.execute("SELECT COUNT(*) FROM vocabulary_words WHERE is_active = 1").fetchone()[0])
        logs = conn.execute(
            "SELECT reviewed_at FROM vocabulary_review_logs WHERE user_id = ? ORDER BY reviewed_at DESC",
            (user_id,),
        ).fetchall()
        source = conn.execute(
            "SELECT id, label, source_url FROM vocabulary_wordlists ORDER BY imported_at DESC LIMIT 1"
        ).fetchone()
        source_rows = conn.execute(
            """
            SELECT category, label, source_url
            FROM vocabulary_wordlist_sources
            WHERE wordlist_id = ?
            ORDER BY CASE category WHEN 'national_core' THEN 0 ELSE 1 END
            """,
            (source["id"],),
        ).fetchall() if source else []
    reviewed_days = {_vocabulary_date(_dt(row["reviewed_at"])) for row in logs}
    streak_days = 0
    cursor = now.astimezone(VOCABULARY_TIMEZONE).date()
    while cursor.isoformat() in reviewed_days:
        streak_days += 1
        cursor -= timedelta(days=1)
    return {
        "date": study_date,
        "daily_new_limit": limit,
        "new_completed": task_counts["new_completed"],
        "review_completed": task_counts["scheduled_review_completed"],
        "same_day_retry_pending": task_counts["retry_pending"],
        "same_day_retry_completed": task_counts["retry_completed"],
        "due_count": due_count,
        "learned_count": learned_count,
        "mastered_count": mastered_count,
        "total_words": total_words,
        "streak_days": streak_days,
        "wordlist_label": source["label"] if source else "上海课程标准依据词表（第三方整理）",
        "source_url": source["source_url"] if source else "",
        "wordlist_sources": [dict(row) for row in source_rows],
    }


def set_vocabulary_daily_new_limit(user_id: str, daily_new_limit: int) -> dict[str, int]:
    if not 10 <= daily_new_limit <= 50:
        raise ValueError("daily_new_limit must be between 10 and 50")
    init_db()
    now = _vocabulary_now()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO vocabulary_settings (user_id, daily_new_limit) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET daily_new_limit = excluded.daily_new_limit
            """,
            (user_id, daily_new_limit),
        )
        added_today = _ensure_vocabulary_daily_cards(conn, user_id, now)
    return {"daily_new_limit": daily_new_limit, "today_new_cards_added": added_today}
