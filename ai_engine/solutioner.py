"""On-demand explanations for a single generated question."""
from __future__ import annotations

from ai_engine.errors import LLMError, SolutionerError
from shared import storage
from shared.schemas import RevisedQuestion, RevisionMode


def generate_solution(
    question: RevisedQuestion,
    *,
    source_question_id: str | None = None,
    revision_mode: RevisionMode | None = None,
) -> str:
    if question.solution:
        return question.solution
    prompt = (
        "Explain this Chinese middle-school English exam question in Chinese. "
        "Return plain text with three short labelled sections: 关键考点、解题思路、易错点. "
        "Do not use a code block.\nQuestion: "
        + question.model_dump_json()
    )
    try:
        from shared.llm.deepseek import get_llm_client
        solution = get_llm_client().text(prompt=prompt, temperature=0.4).strip()
    except LLMError:
        raise
    except Exception as exc:
        raise SolutionerError(f"solution generation failed: {exc}") from exc
    if not solution:
        raise SolutionerError("solution generation returned empty text")
    if source_question_id and revision_mode == "original":
        storage.write_question_solution(source_question_id, solution)
    return solution
