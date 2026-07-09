from __future__ import annotations

import json
import math
import secrets
import sqlite3
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator
from uuid import uuid4

from shared.config import get_config
from shared.schemas import (
    Attempt,
    KPMastery,
    MasteryProfile,
    Paper,
    PaperListItem,
    Session,
    User,
    UserRecord,
)

DB_PATH_OVERRIDE: Path | None = None


def set_db_path(path: str | Path | None) -> None:
    global DB_PATH_OVERRIDE
    DB_PATH_OVERRIDE = Path(path) if path is not None else None


def get_db_path() -> Path:
    return DB_PATH_OVERRIDE or get_config().storage.sqlite_path


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
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
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
                source_question_id TEXT NOT NULL,
                question_type TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                is_correct INTEGER NOT NULL,
                kps_json TEXT NOT NULL,
                PRIMARY KEY (attempt_id, source_question_id)
            );
            CREATE INDEX IF NOT EXISTS idx_att_it_source ON attempt_items(source_question_id);
            """
        )


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
    return User(id=record.id, username=record.username, created_at=record.created_at) if record else None


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
            SELECT paper_id, title, generated_at, payload_json, total_score, submitted
            FROM (
                SELECT paper_id, title, generated_at, payload_json, submitted,
                       json_extract(payload_json, '$.total_score') AS total_score
                FROM papers
                WHERE user_id = ?
            )
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
                total_score=int(row["total_score"] or payload.get("total_score", 0)),
                submitted=bool(row["submitted"]),
            )
        )
    return items


def mark_paper_submitted(paper_id: str) -> None:
    init_db()
    with connect() as conn:
        conn.execute(
            "UPDATE papers SET submitted = 1, submitted_at = ? WHERE paper_id = ?",
            (datetime.now(timezone.utc).isoformat(), paper_id),
        )


def write_attempt(attempt: Attempt) -> str:
    init_db()
    attempt_id = uuid4().hex
    with connect() as conn:
        conn.execute(
            "INSERT INTO attempts (id, user_id, paper_id, answered_at) VALUES (?, ?, ?, ?)",
            (attempt_id, attempt.user_id, attempt.paper_id, attempt.answered_at.isoformat()),
        )
        for item in attempt.items:
            conn.execute(
                """
                INSERT INTO attempt_items
                    (attempt_id, source_question_id, question_type, difficulty, is_correct, kps_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    attempt_id,
                    item.source_question_id,
                    item.question_type,
                    item.difficulty,
                    1 if item.is_correct else 0,
                    json.dumps(item.knowledge_point_ids, ensure_ascii=False),
                ),
            )
    return attempt_id


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
            correct_rate=correct / attempts if attempts else 0.0,
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
