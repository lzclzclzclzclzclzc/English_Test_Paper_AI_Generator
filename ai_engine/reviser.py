"""Reviser module: candidate questions → final Paper.

Three revision strategies:
- original: copy as-is, no LLM call
- light: keep structure, modify vocabulary/context
- fresh: generate completely new question based on KP

Three-layer defense + fallback mechanism.
"""
from __future__ import annotations

import json
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone as tz
from typing import Literal, Tuple

from pydantic import BaseModel, Field

from ai_engine.errors import ReviserError
from ai_engine.prompts import load
from shared.llm.deepseek import get_llm_client
from shared.schemas import (
    GenerateRequest,
    Paper,
    PaperItem,
    Question,
    RevisedQuestion,
    RetrievalResult,
)


def _default_score(question_type: str) -> int:
    """Default score per question type.

    single_choice: 2 points
    word_form: 1 point
    sentence_rewriting: 3 points
    """
    scores = {
        "single_choice": 2,
        "word_form": 1,
        "sentence_rewriting": 3,
    }
    return scores.get(question_type, 2)


def _infer_title(req: GenerateRequest) -> str:
    """Infer a paper title from the request."""
    parts = []
    if req.question_types:
        type_names = {
            "single_choice": "单选",
            "word_form": "词性转换",
            "sentence_rewriting": "改写句子",
        }
        parts.append("、".join(type_names.get(t, t) for t in req.question_types))
    if req.revision_intensity == "original":
        parts.append("原题")
    elif req.revision_intensity == "fresh":
        parts.append("新题")
    if req.total_questions:
        parts.append(f"{req.total_questions}道")
    if parts:
        return "".join(parts) + "练习"
    return "中考英语练习"


def _copy_question(q: Question) -> RevisedQuestion:
    """Copy a Question to RevisedQuestion (original mode)."""
    return RevisedQuestion(
        question_type=q.question_type,
        knowledge_point_ids=q.knowledge_point_ids,
        stem=q.stem,
        options=q.options,
        hint=q.hint,
        original_sentence=q.original_sentence,
        instruction=q.instruction,
        template=q.template,
        answer=q.answer,
    )


def _validate_revision(original: Question, revised: RevisedQuestion) -> bool:
    """Three-layer defense validation.

    Layer 1: Schema validation (handled by pydantic)
    Layer 2: Invariant validation (question_type, KP must match)
    Layer 3: Answer format validation
    """
    # Layer 2: Invariant validation
    if revised.question_type != original.question_type:
        return False
    if set(revised.knowledge_point_ids) != set(original.knowledge_point_ids):
        return False

    # Layer 3: Answer format validation
    qt = original.question_type
    if qt == "single_choice":
        if revised.answer not in {"A", "B", "C", "D"}:
            return False
        if not revised.options or len(revised.options) != 4:
            return False
        labels = {opt.label for opt in revised.options}
        if labels != {"A", "B", "C", "D"}:
            return False
    elif qt in ("word_form", "sentence_rewriting"):
        if not revised.answer or not str(revised.answer).strip():
            return False

    return True


def _revise_one(
    question: Question,
    intensity: Literal["fresh", "light", "original"],
    user_query: str,
) -> Tuple[RevisedQuestion, str | None]:
    """Revise a single question according to revision intensity.

    Returns (RevisedQuestion, revision_notes or None).
    """
    # Original mode: direct copy, no LLM call
    if intensity == "original":
        return _copy_question(question), None

    # Build prompt based on intensity
    kp_names = ", ".join(question.knowledge_point_ids)
    original_dict = question.dict()

    if intensity == "light":
        system_prompt, user_prompt = load(
            "reviser_light",
            original_question=original_dict,
            kp_names=kp_names,
            user_query=user_query,
        )
        temperature = 0.3
    else:  # fresh
        system_prompt, user_prompt = load(
            "reviser_fresh",
            original_question=original_dict,
            kp_names=kp_names,
            user_query=user_query,
        )
        temperature = 0.5

    # LLM call with retry
    client = get_llm_client()
    try:
        revised = client.structured(
            response_model=RevisedQuestion,
            prompt=user_prompt,
            system=system_prompt,
            max_retries=2,
            temperature=temperature,
        )

        # Three-layer defense validation
        if _validate_revision(question, revised):
            return revised, None
        else:
            return _copy_question(question), "revision failed: invariant violation"

    except Exception as e:
        return _copy_question(question), f"revision failed: {str(e)}"


def build_paper(req: GenerateRequest, retrieval: RetrievalResult) -> Paper:
    """Build a complete Paper from retrieval results.

    Processes candidates according to revision_intensity, handles concurrency,
    and assembles the final paper.
    """
    items: list[PaperItem] = []
    num_questions = min(req.total_questions, len(retrieval.items))

    # Process questions concurrently
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = []
        for idx, retrieved in enumerate(retrieval.items[:num_questions], start=1):
            futures.append(
                executor.submit(
                    _revise_one,
                    retrieved.question,
                    req.revision_intensity,
                    req.free_text,
                )
            )

        for idx, future in enumerate(as_completed(futures), start=1):
            rq, notes = future.result()
            items.append(
                PaperItem(
                    index=idx,
                    question=rq,
                    score=_default_score(rq.question_type),
                    source_question_id=retrieval.items[idx - 1].question.id,
                    revision_mode=req.revision_intensity,
                    revision_notes=notes,
                )
            )

    # Collect revision failure indices
    revision_failures = [it.index for it in items if it.revision_notes]

    return Paper(
        paper_id=uuid.uuid4().hex,
        title=_infer_title(req),
        generated_at=datetime.now(tz.utc),
        request=req,
        items=items,
        total_score=sum(it.score for it in items),
        metadata={
            "retrieval_warnings": retrieval.warnings,
            "revision_failures": revision_failures,
            "llm_calls": len(items) - (req.revision_intensity == "original" and len(items)),
        },
    )