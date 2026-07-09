from __future__ import annotations

from typing import Literal

import ai_engine
from shared.schemas import MasteryProfile, Paper, RevisedQuestion, WrongItemRef


def generate_paper(
    user_query: str,
    mode: Literal["fresh", "remediation", "review"] = "fresh",
    *,
    wrong_items: list[WrongItemRef] | None = None,
    user_id: str | None = None,
    review_window_days: int | None = None,
) -> Paper:
    return ai_engine.generate_paper(
        user_query=user_query,
        mode=mode,
        wrong_items=wrong_items,
        user_id=user_id,
        review_window_days=review_window_days,
    )


def revise_paper(current_paper: Paper, user_instruction: str) -> Paper:
    return ai_engine.revise_paper(current_paper, user_instruction)


def generate_solution(
    question: RevisedQuestion,
    *,
    source_question_id: str | None = None,
    revision_mode: Literal["fresh", "light", "original"] | None = None,
) -> str:
    return ai_engine.generate_solution(
        question,
        source_question_id=source_question_id,
        revision_mode=revision_mode,
    )


def build_profile(user_id: str, window_days: int | None = None) -> MasteryProfile:
    return ai_engine.build_profile(user_id, window_days)
