"""Tool definitions for the study-coach agent.

Tools:
  get_user_history       — pull the user's answer record summarised per KP
  get_example_questions  — fetch random bank questions for a KP
  generate_paper         — generate a paper via the AI Engine pipeline
  implement_study_plan   — turn an NL plan into per-day papers + persist

SECURITY: the acting user id is NEVER a tool parameter — the LLM (and the
client-supplied chat history) must not be able to choose whose data a tool
touches. The backend binds the authenticated id via set_current_user_id()
before running the agent; tools read it from a ContextVar.
"""
from __future__ import annotations

import json
import sqlite3
from contextvars import ContextVar

from agents import function_tool

from shared import storage

# Set by the backend (backend/api/agent.py) from current_user before Runner.run.
_current_user_id: ContextVar[str | None] = ContextVar("agent_current_user_id", default=None)


def set_current_user_id(user_id: str | None) -> None:
    """Bind the authenticated user id for the duration of one agent run."""
    _current_user_id.set(user_id)


def _require_user_id() -> str:
    uid = _current_user_id.get()
    if not uid:
        raise RuntimeError("no authenticated user bound for this agent run")
    return uid


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(storage.get_db_path()))
    conn.row_factory = sqlite3.Row
    return conn


@function_tool
def get_user_history(window_days: int = 30) -> str:
    """获取当前用户最近 window_days 天的做题情况，按知识点汇总。

    返回 JSON，每个条目包含：
      knowledge_point_id, level2（中文名）, question_type,
      attempts（做题数）, correct（正确数）, accuracy（正确率 0~1）
    按正确率升序排列（最薄弱的在最前面）。
    """
    user_id = _require_user_id()
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

    if not kp_attempts:
        return json.dumps({"user_id": user_id, "window_days": window_days,
                           "total_items": len(rows), "kp_summary": []},
                          ensure_ascii=False)

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


@function_tool
def implement_study_plan(plan_text: str, start_date: str = "") -> str:
    """将自然语言学习计划转化为结构化计划并生成每日试卷，持久化到数据库。

    Args:
        plan_text: Coach 输出的完整自然语言学习计划文本
        start_date: 计划开始日期，格式 YYYY-MM-DD，空则取今天

    返回 JSON，包含 plan_id 和每日安排摘要（index, kp_name, paper_id, paper_title）。
    """
    from datetime import date, timedelta
    from concurrent.futures import ThreadPoolExecutor

    from agent.plan_extractor import extract_study_plan, _load_valid_kp_ids
    from ai_engine import retriever as _retriever
    from ai_engine import reviser as _reviser
    from shared import storage as _storage
    from shared.schemas import GenerateRequest

    user_id = _require_user_id()

    try:
        parsed_start = date.fromisoformat(start_date) if start_date else date.today()
    except ValueError:
        return json.dumps({"error": f"日期格式无效: {start_date}（应为 YYYY-MM-DD）"},
                          ensure_ascii=False)

    try:
        plan_data = extract_study_plan(plan_text, user_id=user_id, start_date=parsed_start)
    except Exception as e:
        return json.dumps({"error": f"计划解析失败: {e}"}, ensure_ascii=False)

    kp_names = _load_valid_kp_ids()  # {id: 中文名}

    def _build_one_day(day) -> dict:
        """为一天生成一张多考点试卷并落库。返回该天结果（含 error 键表示失败）。"""
        day_kp_names = [kp_names.get(kp, kp) for kp in day.knowledge_points]
        day_date = (parsed_start + timedelta(days=day.index - 1)).isoformat()
        req = GenerateRequest(
            total_questions=day.total_questions,
            knowledge_points=day.knowledge_points,
            question_types=day.question_types,
            revision_intensity="light",
            user_id=user_id,
        )
        try:
            retrieval = _retriever.retrieve(req)
            paper = _reviser.build_paper(req, retrieval)
            _storage.save_paper(paper, user_id)
        except Exception as e:
            return {
                "index": day.index, "date": day_date, "theme": day.theme,
                "knowledge_points": day.knowledge_points, "kp_names": day_kp_names,
                "question_types": day.question_types, "total_questions": day.total_questions,
                "note": day.note, "error": str(e),
            }
        return {
            "index": day.index, "date": day_date, "theme": day.theme,
            "knowledge_points": day.knowledge_points, "kp_names": day_kp_names,
            "question_types": day.question_types, "total_questions": day.total_questions,
            "note": day.note, "paper_id": paper.paper_id, "paper_title": paper.title,
        }

    # 各天相互独立 → 并行生成（每天内部 build_paper 也已并发改题）。
    # 按 index 排序，保证输出与计划天数顺序一致。
    with ThreadPoolExecutor(max_workers=min(len(plan_data.days), 5)) as ex:
        results = sorted(ex.map(_build_one_day, plan_data.days), key=lambda d: d["index"])

    days_out = []
    saved_days = []
    failed_days = []
    for r in results:
        if "error" in r:
            failed_days.append({
                "index": r["index"], "theme": r["theme"], "error": r["error"],
            })
            days_out.append({
                "index": r["index"], "theme": r["theme"],
                "knowledge_points": r["kp_names"], "error": r["error"],
            })
            continue
        days_out.append({
            "index": r["index"], "date": r["date"], "theme": r["theme"],
            "knowledge_points": r["kp_names"],
            "paper_id": r["paper_id"], "paper_title": r["paper_title"],
        })
        saved_days.append({
            "index": r["index"], "date": r["date"], "theme": r["theme"],
            "knowledge_points": r["knowledge_points"], "kp_names": r["kp_names"],
            "question_types": r["question_types"], "total_questions": r["total_questions"],
            "note": r["note"], "paper_id": r["paper_id"], "paper_title": r["paper_title"],
        })

    if not saved_days:
        return json.dumps({"error": "所有天的试卷都生成失败，请稍后重试", "days": days_out},
                          ensure_ascii=False)

    # total_days reflects what was actually saved, not the original intent
    serialisable = {"total_days": len(saved_days), "days": saved_days}
    plan_id = _storage.save_study_plan(user_id, len(saved_days), serialisable)

    # Surface partial failure explicitly so the coach can tell the user which
    # days it couldn't build (requested_days > total_days ⇒ some days failed),
    # rather than silently shrinking the plan.
    return json.dumps({
        "plan_id": plan_id,
        "requested_days": len(plan_data.days),
        "total_days": len(saved_days),
        "failed_days": failed_days,
        "days": days_out,
    }, ensure_ascii=False, indent=2)


@function_tool
def generate_paper(
    user_query: str,
    mode: str = "fresh",
) -> str:
    """根据用户的自然语言请求生成一份英语练习试卷。

    Args:
        user_query: 用户的自然语言出题请求，例如"来10道现在完成时的单选题"
        mode: 出题模式，fresh（普通出题）/ remediation（错题巩固）/ review（复习薄弱点）

    返回试卷的摘要信息（标题、题数、每道题的题干和答案）。
    """
    from ai_engine.pipeline import generate_paper as _generate_paper
    from shared import storage as _storage

    user_id = _require_user_id()

    valid_modes = {"fresh", "remediation", "review"}
    if mode not in valid_modes:
        mode = "fresh"

    try:
        paper = _generate_paper(user_query, mode=mode, user_id=user_id)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

    # Persist so /api/papers/{id} works. A save failure MUST be surfaced —
    # otherwise the agent advertises a paper_id the frontend can't open (404).
    try:
        _storage.save_paper(paper, user_id)
    except Exception as e:
        return json.dumps({"error": f"试卷已生成但保存失败，请重试: {e}"}, ensure_ascii=False)

    # Build a readable summary for the agent
    items = []
    for item in paper.items:
        q = item.question
        entry: dict = {
            "index": item.index,
            "question_type": q.question_type,
            "knowledge_points": q.knowledge_point_ids,
        }
        if q.stem:
            entry["stem"] = q.stem
        if q.original_sentence:
            entry["original_sentence"] = q.original_sentence
        if q.instruction:
            entry["instruction"] = q.instruction
        if q.options:
            entry["options"] = [{"label": o.label, "text": o.text} for o in q.options]
        if q.hint:
            entry["hint"] = q.hint
        entry["answer"] = q.answer if isinstance(q.answer, str) else str(q.answer)
        items.append(entry)

    return json.dumps({
        "paper_id": paper.paper_id,
        "title": paper.title,
        "total_questions": len(paper.items),
        "revision_intensity": paper.request.revision_intensity,
        "items": items,
    }, ensure_ascii=False, indent=2)
