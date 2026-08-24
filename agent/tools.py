"""Tool definitions for the study-coach agent.

Tools:
  get_user_history       — pull the user's answer record summarised per KP
  get_example_questions  — fetch random bank questions for a KP
  generate_paper         — generate a paper via the AI Engine pipeline
  implement_study_plan   — turn an NL plan into per-day papers + persist
  get_vocabulary_status  — summarise the user's spaced-repetition vocab progress
  create_mindmap         — save a new mind map from a markdown outline
  get_current_mindmap    — read the mind map currently being edited
  update_current_mindmap — overwrite the mind map currently being edited

SECURITY: the acting user id is NEVER a tool parameter — the LLM (and the
client-supplied chat history) must not be able to choose whose data a tool
touches. The backend binds the authenticated id via set_current_user_id()
before running the agent; tools read it from a ContextVar. The same holds for
the mind map being edited (set_current_mindmap_id / _current_mindmap_id).
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


# Set by the backend when the agent runs in mindmap-edit context (scope=mindmap).
_current_mindmap_id: ContextVar[str | None] = ContextVar("agent_current_mindmap_id", default=None)


def set_current_mindmap_id(mindmap_id: str | None) -> None:
    """Bind the mindmap being edited for the duration of one agent run."""
    _current_mindmap_id.set(mindmap_id)


def _require_mindmap_id() -> str:
    mid = _current_mindmap_id.get()
    if not mid:
        raise RuntimeError("no mindmap bound for this agent run")
    return mid


def _connect_app() -> sqlite3.Connection:
    conn = sqlite3.connect(str(storage.get_db_path()))
    conn.row_factory = sqlite3.Row
    return conn


def _connect_bank() -> sqlite3.Connection:
    conn = sqlite3.connect(str(storage.get_bank_db_path()))
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
    conn = _connect_app()
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
    conn2 = _connect_bank()
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
def get_vocabulary_status() -> str:
    """获取当前用户的背单词情况（间隔重复词汇模块）。

    返回 JSON，包含：
      today: 今日任务阶段与计数
        - phase（当前阶段：scheduled_review 复习 / new 新词 / same_day_retry 当日重练 / completed 已完成）
        - remaining（今日还剩多少张卡）
        - new_completed / new_total（今日新词进度）
        - review_completed / review_total（今日到期复习进度）
        - daily_new_limit（每日新词上限）
      progress: 累计进度
        - learned_count / total_words（已学 / 词表总量）
        - mastered_count（长期掌握：走完全部复习间隔）
        - due_count（当前到期待复习）
        - streak_days（连续学习天数）
        - wordlist_label（词表名）
    据此可判断学生今天该不该背、进度如何、要不要提醒复习。
    """
    user_id = _require_user_id()
    today = storage.get_vocabulary_today(user_id)
    progress = storage.get_vocabulary_progress(user_id)
    counts = today.get("counts", {})
    return json.dumps({
        "today": {
            "date": today.get("date"),
            "phase": today.get("phase"),
            "daily_new_limit": today.get("daily_new_limit"),
            "remaining": counts.get("remaining_count"),
            "new_completed": counts.get("new_completed"),
            "new_total": counts.get("new_total"),
            "review_completed": counts.get("scheduled_review_completed"),
            "review_total": counts.get("scheduled_review_total"),
            "retry_pending": counts.get("retry_pending"),
        },
        "progress": {
            "learned_count": progress.get("learned_count"),
            "total_words": progress.get("total_words"),
            "mastered_count": progress.get("mastered_count"),
            "due_count": progress.get("due_count"),
            "streak_days": progress.get("streak_days"),
            "wordlist_label": progress.get("wordlist_label"),
        },
    }, ensure_ascii=False, indent=2)


@function_tool
def get_example_questions(knowledge_point_id: str, count: int = 3) -> str:
    """从题库随机抽取该知识点的例题（最多 count 道，默认 3 道）。

    返回 JSON 列表，每道题包含：
      id, question_type, stem（题干）, options（单选选项）,
      hint（词性转换提示词）, original_sentence（改写原句）,
      instruction（改写要求）, answer（正确答案）
    """
    return _example_questions(knowledge_point_id, count)


def _example_questions(knowledge_point_id: str, count: int = 3) -> str:
    """Plain implementation of get_example_questions (unwrapped for testing)."""
    conn = _connect_bank()
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

    from uuid import uuid4

    from agent.plan_extractor import extract_study_plan, _load_valid_kp_ids
    from ai_engine import retriever as _retriever
    from ai_engine import reviser as _reviser
    from backend.errors import InsufficientCreditsError
    from backend.services import credits as _credits
    from shared import storage as _storage
    from shared.schemas import GenerateRequest

    user_id = _require_user_id()
    plan_ref = uuid4().hex

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
        # 积分：每天一卷，按 light × 题数扣；余额不足 → 该天失败（其余天照常）；生成失败退回
        day_ref = f"{plan_ref}:{day.index}"
        try:
            _credits.charge_request(user_id, req, ref_type="plan_day", ref_id=day_ref, note=f"学习计划 第 {day.index} 天")
        except InsufficientCreditsError as e:
            d = e.detail if isinstance(e.detail, dict) else {}
            return {
                "index": day.index, "date": day_date, "theme": day.theme,
                "knowledge_points": day.knowledge_points, "kp_names": day_kp_names,
                "question_types": day.question_types, "total_questions": day.total_questions,
                "note": day.note,
                "error": f"积分不足（需要 {d.get('required')}，可用 {d.get('available')}）",
            }
        try:
            retrieval = _retriever.retrieve(req)
            paper = _reviser.build_paper(req, retrieval)
            _storage.save_paper(paper, user_id)
        except Exception as e:
            _credits.refund(user_id, ref_type="plan_day", ref_id=day_ref, note="计划出卷失败退回")
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
    from backend.errors import InsufficientCreditsError
    from backend.services import credits as _credits
    from shared import storage as _storage

    user_id = _require_user_id()

    valid_modes = {"fresh", "remediation", "review"}
    if mode not in valid_modes:
        mode = "fresh"

    # 积分：与 /api/papers/generate 同一套扣费（解析出强度×题数后扣，失败退回）。
    charge = _credits.PaperCharge(user_id, note="学习助手出卷")
    try:
        paper = _generate_paper(user_query, mode=mode, user_id=user_id, on_request=charge.on_request)
    except InsufficientCreditsError as e:
        d = e.detail if isinstance(e.detail, dict) else {}
        return json.dumps({
            "error": "积分不足",
            "credits_required": d.get("required"),
            "credits_available": d.get("available"),
            "hint": "请告诉用户：这次出卷需要 {} 积分，当前可用 {} 积分，可以去「积分」页充值，或减少题量 / 改用真题原样。".format(
                d.get("required"), d.get("available")),
        }, ensure_ascii=False)
    except Exception as e:
        charge.refund()
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    paper.metadata.update(charge.metadata())

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
        "credits_charged": paper.metadata.get("credits_charged"),
        "items": items,
    }, ensure_ascii=False, indent=2)


@function_tool
def create_mindmap(topic: str, outline_markdown: str) -> str:
    """把一个语法/知识点讲解整理成思维导图并保存（全局聊天场景）。

    Args:
        topic: 思维导图标题，例如"现在完成时"
        outline_markdown: 层级大纲（# 根节点 / ## 分支 / - 叶子），Markmap 格式
    返回 {mindmap_id, title}；大纲非法或保存失败时返回 {error}。
    """
    return _create_mindmap(topic, outline_markdown)


def _create_mindmap(topic: str, outline_markdown: str) -> str:
    user_id = _require_user_id()
    if not outline_markdown or "#" not in outline_markdown:
        return json.dumps({"error": "大纲为空或缺少 # 根节点，请重新组织层级大纲"},
                          ensure_ascii=False)
    title = topic.strip() or "未命名思维导图"
    try:
        mindmap_id = storage.save_mindmap(user_id, title, outline_markdown.strip(),
                                          knowledge_point=title)
    except Exception as e:
        return json.dumps({"error": f"思维导图保存失败，请重试: {e}"}, ensure_ascii=False)
    return json.dumps({"mindmap_id": mindmap_id, "title": title}, ensure_ascii=False)


@function_tool
def get_current_mindmap() -> str:
    """读取当前正在编辑的思维导图大纲（编辑页场景，改图前先读现状）。

    返回 {mindmap_id, title, outline_markdown}；无当前图或不存在时返回 {error}。
    """
    return _get_current_mindmap()


def _get_current_mindmap() -> str:
    user_id = _require_user_id()
    mindmap_id = _require_mindmap_id()
    mm = storage.get_mindmap(user_id, mindmap_id)
    if not mm:
        return json.dumps({"error": "当前思维导图不存在或无权访问"}, ensure_ascii=False)
    return json.dumps({
        "mindmap_id": mm["id"],
        "title": mm["title"],
        "outline_markdown": mm["outline_md"],
    }, ensure_ascii=False)


@function_tool
def update_current_mindmap(outline_markdown: str) -> str:
    """覆盖保存当前正在编辑的思维导图（编辑页场景）。

    Args:
        outline_markdown: 修改后的完整层级大纲（Markmap 格式）
    返回 {ok, mindmap_id}；大纲非法或保存失败时返回 {error}。
    """
    return _update_current_mindmap(outline_markdown)


def _update_current_mindmap(outline_markdown: str) -> str:
    user_id = _require_user_id()
    mindmap_id = _require_mindmap_id()
    if not outline_markdown or "#" not in outline_markdown:
        return json.dumps({"error": "大纲为空或缺少 # 根节点"}, ensure_ascii=False)
    ok = storage.update_mindmap(user_id, mindmap_id, outline_md=outline_markdown.strip())
    if not ok:
        return json.dumps({"error": "保存失败：思维导图不存在或无权访问"}, ensure_ascii=False)
    return json.dumps({"ok": True, "mindmap_id": mindmap_id}, ensure_ascii=False)
