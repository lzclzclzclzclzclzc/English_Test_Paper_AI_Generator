"""Stage 4: load knowledge tree + chapters JSON into SQLite (Spec §3.7).

Reads:
    data/kb/knowledge_tree.json      — reviewed, frozen KP list + mapping
    data/chapters/<book>.json        — chapter_splitter + apply-kp + assign-ids output

Writes:
    data/questions.db                — SQLite database created / updated in place

Idempotent by primary keys:
    * knowledge_points.id, questions.id, (question_id, knowledge_point_id) are
      all primary keys — INSERT OR IGNORE writes each row once.
    * Rerunning after chapters JSON has been edited will INSERT new rows and
      SKIP existing ones. To rebuild fields on existing rows, drop the DB
      (or delete the specific row) first — this is a Loader, not a migrator.

Note: `attempts` / `attempt_items` are created empty. They belong to the future
FastAPI backend (Spec C); this Loader touches only the question bank.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_TREE_PATH    = Path("data/kb/knowledge_tree.json")
DEFAULT_CHAPTERS_DIR = Path("data/chapters")
DEFAULT_DB_PATH      = Path("data/questions.db")
SCHEMA_PATH          = Path(__file__).parent / "schema.sql"


@dataclass
class LoadStats:
    kps_inserted: int = 0
    kps_skipped: int = 0            # already existed
    questions_inserted: int = 0
    questions_skipped: int = 0
    qkp_links_inserted: int = 0
    qkp_links_skipped: int = 0
    per_book: dict[str, int] = field(default_factory=dict)

    def summary(self) -> str:
        lines = [
            f"  knowledge_points:  inserted={self.kps_inserted}  skipped={self.kps_skipped}",
            f"  questions:         inserted={self.questions_inserted}  skipped={self.questions_skipped}",
            f"  question↔KP links: inserted={self.qkp_links_inserted}  skipped={self.qkp_links_skipped}",
        ]
        if self.per_book:
            lines.append("  per book:")
            for b, n in sorted(self.per_book.items()):
                lines.append(f"    {b:24s} {n} questions")
        return "\n".join(lines)


def _now_utc() -> str:
    """ISO-8601 UTC timestamp for `created_at`. Naive → UTC to keep SQLite happy."""
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


def _stem_hash(q: dict) -> str:
    """SHA-256 over the fields that identify a question's content.

    Combines question_type-specific fields:
      * single_choice     — stem + options + answer
      * word_form         — stem + hint + answer
      * sentence_rewriting — original_sentence + instruction + template + answer

    Deterministic: uses `sort_keys=True` + `ensure_ascii=False` so identical
    content across reruns produces identical hashes."""
    payload: dict[str, Any] = {"qt": q["question_type"], "answer": q["answer"]}
    qt = q["question_type"]
    if qt == "single_choice":
        payload["stem"]    = q.get("stem")
        payload["options"] = q.get("options")
    elif qt == "word_form":
        payload["stem"] = q.get("stem")
        payload["hint"] = q.get("hint")
    elif qt == "sentence_rewriting":
        payload["orig"]     = q.get("original_sentence")
        payload["instr"]    = q.get("instruction")
        payload["template"] = q.get("template")
    else:
        raise ValueError(f"unknown question_type: {qt!r}")
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _open_and_init(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    return conn


def _load_kps(
    conn: sqlite3.Connection,
    kps: list[dict],
    stats: LoadStats,
) -> None:
    """INSERT OR IGNORE each KP. Skip existing rows silently."""
    for kp in kps:
        cur = conn.execute(
            "INSERT OR IGNORE INTO knowledge_points (id, level1, level2, aliases_json) "
            "VALUES (?, ?, ?, ?)",
            (kp["id"], kp["level1"], kp["level2"],
             json.dumps(kp.get("aliases", []), ensure_ascii=False)),
        )
        if cur.rowcount:
            stats.kps_inserted += 1
        else:
            stats.kps_skipped += 1


def _load_questions(
    conn: sqlite3.Connection,
    all_questions: list[dict],
    stats: LoadStats,
) -> None:
    """INSERT OR IGNORE each question + its KP links."""
    now = _now_utc()

    for q in all_questions:
        # Serialize the two structured columns as JSON TEXT (Spec §3.7).
        # answer is always present; single_choice's answer is a bare string,
        # so we still json.dumps it — round-trip gives back that same string.
        answer_json  = json.dumps(q["answer"],   ensure_ascii=False)
        options_json = (
            json.dumps(q["options"], ensure_ascii=False)
            if q.get("options") is not None else None
        )

        cur = conn.execute(
            """
            INSERT OR IGNORE INTO questions (
                id, book, question_type, chapter_l1, chapter_l2, number,
                stem, options_json,
                hint,
                original_sentence, instruction, template,
                answer_json, solution,
                source_md, source_line, stem_hash,
                created_at, version
            ) VALUES (?, ?, ?, ?, ?, ?,
                      ?, ?,
                      ?,
                      ?, ?, ?,
                      ?, ?,
                      ?, ?, ?,
                      ?, ?)
            """,
            (
                q["id"], q["book"], q["question_type"],
                q["chapter_l1"], q["chapter_l2"], q["number"],
                q.get("stem"), options_json,
                q.get("hint"),
                q.get("original_sentence"), q.get("instruction"), q.get("template"),
                answer_json, None,             # solution is None on ingestion (§1.5)
                q["source_md"], q["source_line"], _stem_hash(q),
                now, 1,
            ),
        )
        if cur.rowcount:
            stats.questions_inserted += 1
            stats.per_book[q["book"]] = stats.per_book.get(q["book"], 0) + 1
        else:
            stats.questions_skipped += 1

        # Wire up KP links (same idempotency contract).
        for kp_id in q.get("knowledge_point_ids", []):
            link_cur = conn.execute(
                "INSERT OR IGNORE INTO question_knowledge_points "
                "(question_id, knowledge_point_id) VALUES (?, ?)",
                (q["id"], kp_id),
            )
            if link_cur.rowcount:
                stats.qkp_links_inserted += 1
            else:
                stats.qkp_links_skipped += 1


def load(
    tree_path: Path = DEFAULT_TREE_PATH,
    chapters_dir: Path = DEFAULT_CHAPTERS_DIR,
    db_path: Path = DEFAULT_DB_PATH,
) -> LoadStats:
    """Read KB + chapters JSON and populate the SQLite DB in place."""
    tree = json.loads(tree_path.read_text(encoding="utf-8"))
    kps = tree["knowledge_points"]

    # Collect all questions from all books. We keep them in a flat list so a
    # single transaction can commit atomically — if anything blows up mid-load
    # we roll back and leave the DB unchanged.
    all_questions: list[dict] = []
    for book_json in sorted(chapters_dir.glob("*.json")):
        all_questions.extend(json.loads(book_json.read_text(encoding="utf-8")))

    stats = LoadStats()
    conn = _open_and_init(db_path)
    try:
        with conn:                              # implicit BEGIN … COMMIT
            _load_kps(conn, kps, stats)
            _load_questions(conn, all_questions, stats)
    finally:
        conn.close()
    return stats
