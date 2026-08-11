from __future__ import annotations

from typing import Literal

from ai_engine.pipeline import (
    build_profile as run_build_profile,
    build_site_profile as run_build_site_profile,
    generate_paper as run_generate_paper,
    generate_solution as run_generate_solution,
    revise_paper as run_revise_paper,
)
from ai_engine.writing_grader import grade_writing as run_grade_writing
from shared.schemas import MasteryProfile, Paper, RevisedQuestion, WritingGradeResult, WrongItemRef

def generate_paper(
    user_query: str,
    mode: Literal["fresh", "remediation", "review"] = "fresh",
    *,
    wrong_items: list[WrongItemRef] | None = None,
    user_id: str | None = None,
    review_window_days: int | None = None,
) -> Paper:
    return run_generate_paper(
        user_query=user_query,
        mode=mode,
        wrong_items=wrong_items,
        user_id=user_id,
        review_window_days=review_window_days,
    )


def revise_paper(current_paper: Paper, user_instruction: str) -> Paper:
    return run_revise_paper(current_paper, user_instruction)


def generate_solution(
    question: RevisedQuestion,
    *,
    source_question_id: str | None = None,
    revision_mode: Literal["fresh", "light", "original"] | None = None,
    user_answer: str | list[str] | dict[str, str] | None = None,
) -> str:
    return run_generate_solution(
        question,
        source_question_id=source_question_id,
        revision_mode=revision_mode,
        user_answer=user_answer,
    )


def build_profile(user_id: str, window_days: int | None = None) -> MasteryProfile:
    return run_build_profile(user_id, window_days)


def build_site_profile(window_days: int | None = None) -> MasteryProfile:
    return run_build_site_profile(window_days)


def grade_writing(question: RevisedQuestion, user_essay: str) -> WritingGradeResult:
    """Grade an essay using LLM-based multi-dimensional scoring."""
    return run_grade_writing(question, user_essay)
