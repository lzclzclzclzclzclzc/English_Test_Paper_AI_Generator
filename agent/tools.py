"""Tool definitions for the study-coach agent.

Two tools:
  get_user_history   — pull the user's answer record for the last N days,
                       summarised per KP (attempts, correct, accuracy, mastery)
  get_example_questions — fetch up to 3 random bank questions for a KP
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from agents import function_tool

_PROJECT_ROOT = Path(__file__).parent.parent
_DB_PATH = _PROJECT_ROOT / "data" / "questions.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


@function_tool
def get_user_history(user_id: str, window_days: int = 30) -> str:
    """获取用户最近 window_days 天的做题情况，按知识点汇总。

    返回 JSON，每个条目包含：
      knowledge_point_id, level2（中文名）, question_type,
      attempts（做题数）, correct（正确数）, accuracy（正确率 0~1）
    按正确率升序排列（最薄弱的在最前面）。
    """
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT ai.kps_json, ai.question_type, ai.is_correct
            FROM attempts a
            JOIN attempt_items ai ON a.id = ai.attempt_id
            WHERE a.user_id = ?
              AND a.answered_at >= datetime('now', '-' || ? || ' days')
            """,
            (user_id, window_days),
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return json.dumps({"user_id": user_id, "window_days": window_days,
                           "total_items": 0, "kp_summary": []},
                          ensure_ascii=False)

    from collections import defaultdict
    kp_attempts: dict[str, int] = defaultdict(int)
    kp_correct: dict[str, int] = defaultdict(int)
    kp_type: dict[str, str] = {}

    for row in rows:
        kp_ids = json.loads(row["kps_json"]) if row["kps_json"] else []
        for kp_id in kp_ids:
            kp_attempts[kp_id] += 1
            if row["is_correct"]:
                kp_correct[kp_id] += 1
            kp_type[kp_id] = row["question_type"]

    # resolve level2 names
    conn2 = _connect()
    try:
        ph = ",".join("?" * len(kp_attempts))
        kp_names = {
            r["id"]: r["level2"]
            for r in conn2.execute(
                f"SELECT id, level2 FROM knowledge_points WHERE id IN ({ph})",
                list(kp_attempts.keys()),
            )
        }
    finally:
        conn2.close()

    summary = []
    for kp_id, n in kp_attempts.items():
        correct = kp_correct[kp_id]
        summary.append({
            "knowledge_point_id": kp_id,
            "level2": kp_names.get(kp_id, kp_id),
            "question_type": kp_type.get(kp_id, ""),
            "attempts": n,
            "correct": correct,
            "accuracy": round(correct / n, 3),
        })

    summary.sort(key=lambda x: x["accuracy"])
    return json.dumps({
        "user_id": user_id,
        "window_days": window_days,
        "total_items": len(rows),
        "kp_summary": summary,
    }, ensure_ascii=False, indent=2)


@function_tool
def get_example_questions(knowledge_point_id: str, count: int = 3) -> str:
    """从题库随机抽取该知识点的例题（最多 count 道，默认 3 道）。

    返回 JSON 列表，每道题包含：
      id, question_type, stem（题干）, options（单选选项）,
      hint（词性转换提示词）, original_sentence（改写原句）,
      instruction（改写要求）, answer（正确答案）
    """
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT q.id, q.question_type, q.stem, q.options_json,
                   q.hint, q.original_sentence, q.instruction,
                   q.template, q.answer_json
            FROM questions q
            JOIN question_knowledge_points qk ON q.id = qk.question_id
            WHERE qk.knowledge_point_id = ?
            ORDER BY RANDOM()
            LIMIT ?
            """,
            (knowledge_point_id, count),
        ).fetchall()
    finally:
        conn.close()

    questions = []
    for row in rows:
        questions.append({
            "id": row["id"],
            "question_type": row["question_type"],
            "stem": row["stem"],
            "options": json.loads(row["options_json"]) if row["options_json"] else None,
            "hint": row["hint"],
            "original_sentence": row["original_sentence"],
            "instruction": row["instruction"],
            "template": row["template"],
            "answer": json.loads(row["answer_json"]),
        })

    return json.dumps({
        "knowledge_point_id": knowledge_point_id,
        "count": len(questions),
        "questions": questions,
    }, ensure_ascii=False, indent=2)
