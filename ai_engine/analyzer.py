"""Analyzer module: user_id + time window → mastery profile.

Reads the user's answer history (attempts / attempt_items) and produces a
MasteryProfile ranking knowledge points by mastery (Wilson score lower bound).
Consumed by the Parser in `review` mode to target weak knowledge points.

Read-only: never modifies any persisted state (Spec B §7.4).
"""
from __future__ import annotations

import json
import math
import sqlite3
from collections import defaultdict

from shared.schemas import KPMastery, MasteryProfile


def _db_path() -> str:
    """Resolve the question DB path, honouring a storage test override.

    analyzer reads the same DB storage writes to; when a caller (tests, or a
    future multi-tenant setup) overrides the path via storage.set_db_path, we
    must follow it — otherwise admin/mastery reads hit the default DB while
    writes go to the override. Falls back to get_config().db_path."""
    from shared import storage

    return str(storage.get_db_path())

# Number of weakest KPs to surface (Spec B §7.2).
DEFAULT_WEAK_KP_LIMIT = 8
# Number of dominant (most-wrong) question types to surface.
DEFAULT_DOMINANT_TYPES_LIMIT = 3


def _wilson_lower(correct: int, total: int, z: float = 1.96) -> float:
    """Wilson score lower bound (95% by default).

    Down-weights low-sample KPs so "1 attempt, wrong" doesn't rank above
    "20 attempts, 60% correct". total=0 → 0.0 (treated as weakest)."""
    if total == 0:
        return 0.0
    p = correct / total
    denom = 1 + z * z / total
    centre = p + z * z / (2 * total)
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))
    return (centre - margin) / denom


def _fetch_attempt_items(
    db_path: str, user_id: str, window_days: int | None
) -> list[sqlite3.Row]:
    """Fetch the user's answered items, optionally limited to the last N days.

    window_days None → all history. The single SQL handles both cases via the
    `? IS NULL OR ...` guard (parameter bound twice)."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT ai.kps_json, ai.question_type, ai.is_correct
            FROM attempts a
            JOIN attempt_items ai ON a.id = ai.attempt_id
            WHERE a.user_id = ?
              AND (? IS NULL OR a.answered_at >= datetime('now', '-' || ? || ' days'))
            """,
            (user_id, window_days, window_days),
        ).fetchall()
        return rows
    finally:
        conn.close()


def _fetch_all_attempt_items(
    db_path: str, window_days: int | None
) -> list[sqlite3.Row]:
    """Fetch ALL users' answered items, optionally limited to the last N days.

    Site-wide counterpart of _fetch_attempt_items (no user_id filter)."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT ai.kps_json, ai.question_type, ai.is_correct
            FROM attempts a
            JOIN attempt_items ai ON a.id = ai.attempt_id
            WHERE (? IS NULL OR a.answered_at >= datetime('now', '-' || ? || ' days'))
            """,
            (window_days, window_days),
        ).fetchall()
        return rows
    finally:
        conn.close()


def build_profile(user_id: str, window_days: int | None = None) -> MasteryProfile:
    """Build a user's mastery profile from attempt history.

    Args:
        user_id: whose history to analyse
        window_days: only consider attempts within the last N days; None = all

    Returns:
        MasteryProfile with weak_kps (ascending mastery, top N), dominant_types
        (most-wrong question types, top 3), and total_attempts_considered.
        Empty profile when there's no history (Spec B §7.3).
    """
    rows = _fetch_attempt_items(_db_path(), user_id, window_days)
    return _reduce_profile(rows, user_id, window_days)


def build_site_profile(window_days: int | None = None) -> MasteryProfile:
    """Site-wide mastery profile aggregated across ALL users' attempt history.

    Same reduction as build_profile but with no user_id filter — used by the
    admin analytics dashboard to surface which knowledge points the whole
    student body struggles with. Read-only, no LLM. user_id is "__all__" as a
    sentinel (the profile is not tied to a single user)."""
    rows = _fetch_all_attempt_items(_db_path(), window_days)
    return _reduce_profile(rows, "__all__", window_days)


def _reduce_profile(
    rows: list[sqlite3.Row], user_id: str, window_days: int | None
) -> MasteryProfile:
    """Reduce answered-item rows to a MasteryProfile. Shared by single-user
    (build_profile) and site-wide (build_site_profile) aggregation."""
    if not rows:
        return MasteryProfile(
            user_id=user_id,
            window_days=window_days,
            weak_kps=[],
            dominant_types=[],
            total_attempts_considered=0,
        )

    # Per-KP tallies: each item counts once per KP it hits (Spec B §7.2).
    kp_attempts: dict[str, int] = defaultdict(int)
    kp_correct: dict[str, int] = defaultdict(int)
    # Per-type wrong counts, for dominant_types.
    type_wrong: dict[str, int] = defaultdict(int)

    for row in rows:
        is_correct = bool(row["is_correct"])
        if not is_correct:
            type_wrong[row["question_type"]] += 1

        kp_ids = json.loads(row["kps_json"]) if row["kps_json"] else []
        for kp_id in kp_ids:
            kp_attempts[kp_id] += 1
            if is_correct:
                kp_correct[kp_id] += 1

    # Wilson score per KP → ascending mastery, take top N weakest.
    kp_masteries = [
        KPMastery(
            knowledge_point_id=kp_id,
            attempts=kp_attempts[kp_id],
            mastery=_wilson_lower(kp_correct[kp_id], kp_attempts[kp_id]),
        )
        for kp_id in kp_attempts
    ]
    kp_masteries.sort(key=lambda k: (k.mastery, k.knowledge_point_id))
    weak_kps = kp_masteries[:DEFAULT_WEAK_KP_LIMIT]

    # Dominant types: most wrong answers first, take top 3.
    dominant_types = [
        qt for qt, _ in sorted(
            type_wrong.items(), key=lambda kv: (-kv[1], kv[0])
        )
    ][:DEFAULT_DOMINANT_TYPES_LIMIT]

    return MasteryProfile(
        user_id=user_id,
        window_days=window_days,
        weak_kps=weak_kps,
        dominant_types=dominant_types,
        total_attempts_considered=len(rows),
    )
