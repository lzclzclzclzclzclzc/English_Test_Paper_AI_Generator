"""Solutioner module: generate an explanation for a single question on demand.

Called when the user clicks "查看解析". Every call goes to the LLM — no
write-back cache. This keeps explanations personalised: when user_answer is
provided the LLM explains why that specific wrong answer is incorrect.
"""
from __future__ import annotations

from shared.config import get_config
from shared.llm.deepseek import get_llm_client
from shared.schemas import Answer, RevisedQuestion, RevisionMode
from ai_engine.errors import SolutionerError
from ai_engine.prompts import load


def _format_answer(answer: Answer) -> str:
    """Render an Answer into human-readable text for the prompt.

    Single-choice is a bare label ("B") — returned as-is. Fill-in is a list of
    candidate blank-groups (list[dict[blank -> [candidates]]]); we render each
    group as "blank1: a / b  blank2: c" and join multiple groups with " 或 "
    so the LLM sees the acceptable answers plainly instead of a raw dict repr
    (which hurts word_form / sentence_rewriting explanations)."""
    if isinstance(answer, str):
        return answer
    # 阅读首字母填空：answer 是多个单空 dict（[{blank1},{blank2},…]），语义是
    # "所有空一起正确"，而非"或"的候选组合 → 逐空分行展示，避免 LLM 只解析一个空
    if answer and all(isinstance(g, dict) and len(g) == 1 for g in answer):
        lines: list[str] = []
        for g in answer:
            blank, cands = next(iter(g.items()))
            lines.append(f"{blank}: {' / '.join(cands)}")
        return "\n".join(lines)
    groups: list[str] = []
    for group in answer:
        blanks = "  ".join(
            f"{blank}: {' / '.join(cands)}" for blank, cands in group.items()
        )
        groups.append(blanks)
    return " 或 ".join(groups)



def _kp_level2_names(db_path: str, kp_ids: list[str]) -> list[str]:
    """Map KP ids to their level2 中文 names for the prompt."""
    if not kp_ids:
        return []
    import sqlite3
    conn = sqlite3.connect(db_path)
    try:
        placeholders = ",".join("?" * len(kp_ids))
        rows = conn.execute(
            f"SELECT id, level2 FROM knowledge_points WHERE id IN ({placeholders})",
            kp_ids,
        ).fetchall()
    finally:
        conn.close()
    name_map = {r[0]: r[1] for r in rows}
    return [name_map.get(kp_id, kp_id) for kp_id in kp_ids]


def _format_user_answer(user_answer: str | list[str] | dict[str, str] | None) -> str:
    """Render the user's (wrong) submitted answer into readable prompt text.

    Single-choice is a bare label ("B"). Fill-in is a list (by blank order) or
    a {blankN: text} dict — rendered as "blank1: went  blank2: to" so the LLM
    can pinpoint which blank the student got wrong."""
    if not user_answer:
        return ""
    if isinstance(user_answer, str):
        return user_answer.strip()
    if isinstance(user_answer, list):
        parts = [f"blank{i}: {v}" for i, v in enumerate(user_answer, start=1) if str(v).strip()]
        return "  ".join(parts)
    # dict
    parts = [f"{k}: {v}" for k, v in user_answer.items() if str(v).strip()]
    return "  ".join(parts)


def generate_solution(
    q: RevisedQuestion,
    *,
    source_question_id: str | None = None,
    revision_mode: RevisionMode | None = None,
    user_answer: str | list[str] | dict[str, str] | None = None,
) -> str:
    """Generate (or fetch cached) an explanation for one question.

    Args:
        q: the question to explain (revised or original)
        source_question_id: id of the bank question this traces back to, if any
        revision_mode: how q was produced ("original"/"light"/"fresh"); only
            "original" is cache-eligible (light/fresh have altered content)

    Returns:
        Plain-text solution (three-section format, see prompts/solutioner.md).
    """
    cfg = get_config()
    db_path = str(cfg.db_path)

    # 2. LLM call
    kp_names = _kp_level2_names(db_path, q.knowledge_point_ids)
    options_text = ""
    if q.options:
        options_text = "\n".join(f"{o.label}. {o.text}" for o in q.options)

    system_prompt, user_prompt = load(
        "solutioner",
        question=q.model_dump(),
        kp_names="、".join(kp_names) if kp_names else "（无）",
        options_text=options_text,
        answer=_format_answer(q.answer),
        wrong_answer=_format_user_answer(user_answer),
    )

    client = get_llm_client()
    try:
        solution = client.text(
            prompt=user_prompt,
            system=system_prompt,
            temperature=0.4,
        )
    except Exception as e:
        raise SolutionerError(f"LLM call failed: {e}") from e

    solution = solution.strip()
    if not solution:
        raise SolutionerError("LLM returned an empty solution")

    return solution
