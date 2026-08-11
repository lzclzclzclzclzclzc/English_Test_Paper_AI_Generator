"""Inject demo attempt history for a test user.

Usage:
    python agent/seed_demo.py [--user USER_ID] [--clear]

Options:
    --user    User ID to seed (default: u_demo_review)
    --clear   Only clear existing data, don't insert new rows

Seeds 12 knowledge points with controlled accuracy:
  - 4 weak KPs  (accuracy ~20-30%)
  - 3 medium KPs (accuracy ~50-60%)
  - 5 strong KPs (accuracy ~80-90%)
"""
from __future__ import annotations

import argparse
import json
import random
import sqlite3
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from shared import storage
from shared.config import get_config

KP_PLAN: list[tuple[str, float, int]] = [
    # (kp_id, target_accuracy, n_attempts)
    # --- weak ---
    ("kp_sc_verbs",           0.20, 20),
    ("kp_sc_prepositions",    0.25, 16),
    ("kp_sr_passive_voice",   0.15, 12),
    ("kp_wf_verb_to_noun",    0.30, 10),
    # --- medium ---
    ("kp_sc_adverb",          0.55, 14),
    ("kp_sc_articles",        0.50,  8),
    ("kp_sc_modal_verbs",     0.60, 10),
    # --- strong ---
    ("kp_sc_adjective",       0.85, 18),
    ("kp_sc_communication",   0.80, 15),
    ("kp_sc_indef_pronoun",   0.90, 12),
    ("kp_sr_word_ordering",   0.85, 10),
    ("kp_wf_noun_plural",     0.75,  8),
]


def _kp_to_type(kp_id: str) -> str:
    if kp_id.startswith("kp_sc_"):
        return "single_choice"
    if kp_id.startswith("kp_wf_"):
        return "word_form"
    return "sentence_rewriting"


def clear_user(conn: sqlite3.Connection, user_id: str) -> int:
    old_ids = [r[0] for r in conn.execute(
        "SELECT id FROM attempts WHERE user_id = ?", (user_id,)
    )]
    if not old_ids:
        return 0
    ph = ",".join("?" * len(old_ids))
    conn.execute(f"DELETE FROM attempt_items WHERE attempt_id IN ({ph})", old_ids)
    conn.execute("DELETE FROM attempts WHERE user_id = ?", (user_id,))
    return len(old_ids)


def seed_user(conn: sqlite3.Connection, bank_conn: sqlite3.Connection, user_id: str, seed: int = 42) -> dict:
    rng = random.Random(seed)
    base_ts = int(time.time())

    attempt_used: dict[str, set[str]] = {}
    attempt_item_index: dict[str, int] = {}  # per-attempt item counter

    def _new_attempt(seq: int) -> str:
        aid = f"att_{user_id}_{base_ts}_{seq}"
        conn.execute(
            "INSERT INTO attempts (id, user_id, paper_id, answered_at) "
            "VALUES (?, ?, 'p_demo', datetime('now'))",
            (aid, user_id),
        )
        attempt_used[aid] = set()
        attempt_item_index[aid] = 0
        return aid

    attempts_pool = [_new_attempt(i) for i in range(3)]

    stats: list[dict] = []
    for kp_id, target_acc, n in KP_PLAN:
        qtype = _kp_to_type(kp_id)
        # fetch distinct question ids for this KP — questions/question_knowledge_points
        # live in the bank DB, so this read uses the bank connection.
        rows = bank_conn.execute(
            """
            SELECT q.id FROM questions q
            JOIN question_knowledge_points qk ON q.id = qk.question_id
            WHERE qk.knowledge_point_id = ?
            ORDER BY q.id
            """,
            (kp_id,),
        ).fetchall()
        source_ids = [r[0] for r in rows] or ["q_unknown"]

        correct = 0
        for i in range(n):
            src = source_ids[i % len(source_ids)]
            aid = next(
                (a for a in attempts_pool if src not in attempt_used[a]),
                None,
            )
            if aid is None:
                aid = _new_attempt(len(attempts_pool))
                attempts_pool.append(aid)

            is_correct = 1 if rng.random() < target_acc else 0
            correct += is_correct
            attempt_item_index[aid] += 1
            conn.execute(
                "INSERT INTO attempt_items "
                "(attempt_id, item_index, source_question_id, question_type, is_correct, kps_json) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (aid, attempt_item_index[aid], src, qtype, is_correct, json.dumps([kp_id])),
            )
            attempt_used[aid].add(src)

        stats.append({
            "kp_id": kp_id,
            "question_type": qtype,
            "attempts": n,
            "correct": correct,
            "accuracy": f"{correct/n*100:.0f}%",
        })

    return {"user_id": user_id, "kp_count": len(KP_PLAN), "stats": stats}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default="test", help="用户ID")
    parser.add_argument("--clear", action="store_true", help="只清除数据，不插入")
    args = parser.parse_args()

    cfg = get_config()
    # User data (attempts/attempt_items) lives in the app DB; questions live in
    # the bank DB. Ensure the app user tables exist, then open one connection
    # per DB.
    storage.init_db()
    conn = sqlite3.connect(str(cfg.app_db_path))
    conn.row_factory = sqlite3.Row
    bank_conn = sqlite3.connect(str(cfg.db_path))
    bank_conn.row_factory = sqlite3.Row

    try:
        cleared = clear_user(conn, args.user)
        if cleared:
            print(f"已清除 {args.user} 的 {cleared} 条历史 attempt 记录")

        if args.clear:
            conn.commit()
            print("完成（仅清除）")
            return

        result = seed_user(conn, bank_conn, args.user)
        conn.commit()

        print(f"\n✅ 注入完成：用户={args.user}，覆盖 {result['kp_count']} 个知识点\n")
        print(f"{'知识点':<30} {'题型':<20} {'做题数':>6} {'正确':>6} {'正确率':>6}")
        print("─" * 72)
        for s in sorted(result["stats"], key=lambda x: x["accuracy"]):
            print(f"{s['kp_id']:<30} {s['question_type']:<20} "
                  f"{s['attempts']:>6} {s['correct']:>6} {s['accuracy']:>6}")
        print()
        print(f"现在可以运行：python agent/run.py --user {args.user} --days 7")

    finally:
        conn.close()
        bank_conn.close()


if __name__ == "__main__":
    main()
