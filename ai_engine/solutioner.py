"""Solutioner module: generate an explanation for a single question on demand.

Called when the user clicks "生成解析" (through the future FastAPI layer). This
is the ONLY AI Engine module with a write side-effect: when the question is an
untouched original bank question, the generated solution is cached back to
`questions.solution` (Spec A §2.7 invariant 6 / Spec B §6).

Flow (Spec B §6.2):
  1. cache lookup   — source_question_id present AND revision_mode == "original"
                      AND questions.solution NOT NULL → return it, no LLM call
  2. LLM call       — DeepSeekClient.text() (the only module using text(), not
                      structured()); plain-text three-section output
  3. write-back     — source_question_id present AND revision_mode == "original"
                      AND questions.solution IS NULL → UPDATE (guarded by
                      `WHERE solution IS NULL` for concurrent-write safety)
  4. return solution text
"""
from __future__ import annotations

import sqlite3

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
    groups: list[str] = []
    for group in answer:
        blanks = "  ".join(
            f"{blank}: {' / '.join(cands)}" for blank, cands in group.items()
        )
        groups.append(blanks)
    return " 或 ".join(groups)



def _fetch_cached_solution(db_path: str, question_id: str) -> str | None:
    """Return the stored solution for a bank question, or None if absent/NULL."""
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT solution FROM questions WHERE id = ?", (question_id,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return row[0]  # may be None


def _kp_level2_names(db_path: str, kp_ids: list[str]) -> list[str]:
    """Map KP ids to their level2 中文 names for the prompt. Unknown ids are
    kept as-is so the prompt still carries some signal."""
    if not kp_ids:
        return []
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


def _write_back_solution(db_path: str, question_id: str, solution: str) -> None:
    """Cache the solution back to the bank, only if still NULL.

    `WHERE solution IS NULL` makes concurrent writes safe: only the first write
    wins, later ones match 0 rows and are silently dropped (Spec B §6.2)."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE questions SET solution = ? WHERE id = ? AND solution IS NULL",
            (solution, question_id),
        )
        conn.commit()
    finally:
        conn.close()


def generate_solution(
    q: RevisedQuestion,
    *,
    source_question_id: str | None = None,
    revision_mode: RevisionMode | None = None,
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

    is_original = source_question_id is not None and revision_mode == "original"

    # 1. cache lookup (original only)
    if is_original:
        cached = _fetch_cached_solution(db_path, source_question_id)
        if cached:
            return cached

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

    # 3. write-back (original only, guarded by solution IS NULL)
    if is_original:
        _write_back_solution(db_path, source_question_id, solution)

    # 4. return
    return solution
