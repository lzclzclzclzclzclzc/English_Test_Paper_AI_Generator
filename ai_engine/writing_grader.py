"""Writing Grader: grade an English essay using LLM-based three-dimensional scoring.

Called when the user submits a writing question. Returns a structured result
with total score, per-dimension scores, and optional detailed analysis (member-only).
"""
from __future__ import annotations

from shared.config import get_config
from shared.llm.deepseek import get_llm_client
from shared.schemas import RevisedQuestion, WritingGradeResult
from ai_engine.errors import SolutionerError
from ai_engine.prompts import load


def grade_writing(
    q: RevisedQuestion,
    user_essay: str,
) -> WritingGradeResult:
    """Grade a student essay using three-dimensional scoring framework.

    Args:
        q: the writing question (contains stem, hint, instruction, reference_expressions, min_words)
        user_essay: the student's essay text

    Returns:
        WritingGradeResult with total_score, per-dimension scores, and detailed analysis.
        Detailed analysis fields are filled regardless of membership status;
        the backend will null them out for non-members before sending to frontend.
    """
    if q.question_type != "writing":
        raise ValueError(f"grade_writing called with non-writing question_type: {q.question_type}")

    system_prompt, user_prompt = load(
        "writing",
        stem=q.stem or "",
        hint=q.hint or "",
        instruction=q.instruction or "",
        reference_expressions=q.reference_expressions or "",
        min_words=str(q.min_words or 60),
        user_essay=user_essay,
    )

    client = get_llm_client()
    try:
        response = client.structured(
            prompt=user_prompt,
            system=system_prompt,
            response_model=WritingGradeResult,
            temperature=0.3,  # Lower temperature for more consistent scoring
        )
    except Exception as e:
        raise SolutionerError(f"LLM call failed: {e}") from e

    # response is already a WritingGradeResult instance (validated by pydantic)
    result = response
    
    # Clamp scores to valid ranges
    result.total_score = max(0.0, min(20.0, result.total_score))
    result.content_score = max(0.0, min(8.0, result.content_score))
    result.language_score = max(0.0, min(8.0, result.language_score))
    result.organization_score = max(0.0, min(4.0, result.organization_score))
    
    # Infer level from total_score if not set or invalid
    valid_levels = ["优秀", "良好", "合格", "待提升"]
    if result.level not in valid_levels:
        if result.total_score >= 17:
            result.level = "优秀"
        elif result.total_score >= 13:
            result.level = "良好"
        elif result.total_score >= 9:
            result.level = "合格"
        else:
            result.level = "待提升"

    return result