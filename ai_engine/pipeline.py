from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from shared import storage
from shared.schemas import (
    GenerateRequest,
    MasteryProfile,
    Option,
    Paper,
    PaperItem,
    RevisedQuestion,
    WrongItemRef,
)


def generate_paper(
    user_query: str,
    mode: Literal["fresh", "remediation", "review"] = "fresh",
    *,
    wrong_items: list[WrongItemRef] | None = None,
    user_id: str | None = None,
    review_window_days: int | None = None,
) -> Paper:
    total_questions = _infer_total_questions(user_query)
    question_types = _infer_question_types(user_query)
    req = GenerateRequest(
        mode=mode,
        question_types=question_types,
        total_questions=total_questions,
        total_score=total_questions * 5,
        revision_intensity="fresh",
        wrong_items=wrong_items or [],
        user_id=user_id,
        review_window_days=review_window_days,
        free_text=user_query,
    )
    items = [_make_item(index, question_types[(index - 1) % len(question_types)]) for index in range(1, total_questions + 1)]
    return Paper(
        paper_id=uuid4().hex,
        title=_infer_title(user_query, mode),
        generated_at=datetime.now(timezone.utc),
        request=req,
        items=items,
        total_score=sum(item.score for item in items),
        metadata={"engine": "deterministic-fake", "mode": mode},
    )


def revise_paper(current_paper: Paper, user_instruction: str) -> Paper:
    old = current_paper.model_copy(deep=True)
    return Paper(
        paper_id=uuid4().hex,
        title=f"{old.title} (revised)",
        generated_at=datetime.now(timezone.utc),
        request=old.request.model_copy(update={"free_text": user_instruction}),
        items=[
            item.model_copy(
                update={
                    "revision_mode": "light",
                    "revision_notes": user_instruction,
                    "question": item.question.model_copy(update={"stem": f"{item.question.stem} [{user_instruction}]"}),
                },
                deep=True,
            )
            for item in old.items
        ],
        total_score=old.total_score,
        metadata={**old.metadata, "revised_from": old.paper_id},
    )


def generate_solution(
    q: RevisedQuestion,
    *,
    source_question_id: str | None = None,
    revision_mode: Literal["fresh", "light", "original"] | None = None,
) -> str:
    return q.solution or f"答案是 {q.answer}。题型为 {q.question_type}，按题干要求作答即可。"


def build_profile(user_id: str, window_days: int | None = None) -> MasteryProfile:
    return storage.build_mastery_profile(user_id, window_days)


def _infer_total_questions(text: str) -> int:
    match = re.search(r"(\d+)", text)
    if not match:
        return 3
    return max(1, min(20, int(match.group(1))))


def _infer_question_types(text: str) -> list[Literal["single_choice", "word_form", "sentence_rewriting"]]:
    types: list[Literal["single_choice", "word_form", "sentence_rewriting"]] = []
    if "选择" in text or "choice" in text.lower():
        types.append("single_choice")
    if "词" in text or "word" in text.lower():
        types.append("word_form")
    if "改写" in text or "rewrite" in text.lower():
        types.append("sentence_rewriting")
    return types or ["single_choice", "word_form", "sentence_rewriting"]


def _infer_title(text: str, mode: str) -> str:
    clean = text.strip()[:24] or mode
    return f"{clean} - 英语练习"


def _make_item(index: int, question_type: Literal["single_choice", "word_form", "sentence_rewriting"]) -> PaperItem:
    if question_type == "single_choice":
        question = RevisedQuestion(
            stem=f"Choose the correct answer for question {index}.",
            question_type="single_choice",
            options=[
                Option(label="A", text="go"),
                Option(label="B", text="goes"),
                Option(label="C", text="went"),
                Option(label="D", text="gone"),
            ],
            answer="B",
            knowledge_point_ids=["kp_single_choice_basic"],
        )
    elif question_type == "word_form":
        question = RevisedQuestion(
            stem=f"Fill in the blank with the correct form: He has ___ (write) question {index}.",
            question_type="word_form",
            options=None,
            hint="write",
            answer=[{"blank1": ["written"]}],
            knowledge_point_ids=["kp_word_form_participle"],
        )
    else:
        question = RevisedQuestion(
            stem=None,
            question_type="sentence_rewriting",
            options=None,
            original_sentence=f"He is too young to go to school. (question {index})",
            instruction="保持句意基本不变",
            template="He is ________ young ________ he cannot go to school.",
            answer=[{"blank1": ["so"], "blank2": ["that"]}],
            knowledge_point_ids=["kp_sentence_rewriting_so_that"],
        )
    return PaperItem(
        index=index,
        question=question,
        score=5,
        source_question_id=f"fake_q_{index:04d}",
        revision_mode="fresh",
        revision_notes="Generated by deterministic fake engine.",
    )
