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


def _infer_title(req: GenerateRequest) -> str:
    """Infer a paper title from the request."""
    parts = []
    if req.question_types:
        type_names = {
            "single_choice": "单选",
            "word_form": "词性转换",
            "sentence_rewriting": "改写句子",
            "listening_single_choice": "听力选择",
            "listening_true_false": "听力判断",
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
        passage_id=q.passage_id,
        passage_json=q.passage_json,
        answer=q.answer,
    )


def _validate_revision(original: Question, revised: RevisedQuestion) -> bool:
    """Three-layer defense validation.

    Layer 1: Schema validation (handled by pydantic)
    Layer 2: Invariant validation (question_type, KP must match)
    Layer 3: Answer format validation
    """
    if revised.question_type != original.question_type:
        return False
    if set(revised.knowledge_point_ids) != set(original.knowledge_point_ids):
        return False

    qt = original.question_type
    if qt in ("single_choice", "listening_single_choice"):
        if revised.answer not in {"A", "B", "C", "D"}:
            return False
        if not revised.options or len(revised.options) != 4:
            return False
        labels = {opt.label for opt in revised.options}
        if labels != {"A", "B", "C", "D"}:
            return False
    elif qt == "listening_true_false":
        if revised.answer not in {"T", "F"}:
            return False
        if not revised.options or len(revised.options) != 2:
            return False
        labels = {opt.label for opt in revised.options}
        if labels != {"T", "F"}:
            return False
    elif qt in ("word_form", "sentence_rewriting"):
        if not revised.answer or not str(revised.answer).strip():
            return False

    return True


def _revise_one(
    question: Question,
    intensity: Literal["fresh", "light", "original"],
    free_text: str,
) -> tuple[RevisedQuestion, bool]:
    """Revise a single question according to revision intensity.

    Returns (revised_question, is_fallback). `is_fallback` is True when a
    light/fresh revision failed (validation rejected the LLM output, or the
    LLM call raised) and we fell back to copying the original. `original`
    mode is never a fallback — copying is its intended behaviour.
    """
    if intensity == "original":
        return _copy_question(question), False

    kp_names = ", ".join(question.knowledge_point_ids)
    original_dict = question.model_dump()

    if intensity == "light":
        system_prompt, user_prompt = load(
            "reviser_light",
            original_question=original_dict,
            kp_names=kp_names,
            user_query=free_text,
        )
        temperature = 0.3
    else:
        system_prompt, user_prompt = load(
            "reviser_fresh",
            original_question=original_dict,
            kp_names=kp_names,
            user_query=free_text,
        )
        temperature = 0.5

    client = get_llm_client()
    try:
        revised = client.structured(
            response_model=RevisedQuestion,
            prompt=user_prompt,
            system=system_prompt,
            max_retries=2,
            temperature=temperature,
        )

        if _validate_revision(question, revised):
            # Force-preserve passage fields for listening_true_false — the
            # passage is shared across a group of questions and must stay
            # identical across all of them. The Reviser processes questions
            # independently (and in parallel), so any per-question passage
            # edit would break group consistency. Passage integrity trumps
            # the revision_intensity passage rule from the design doc.
            if question.question_type == "listening_true_false":
                revised.passage_id = question.passage_id
                revised.passage_json = question.passage_json
            return revised, False
        else:
            return _copy_question(question), True

    except Exception:
        return _copy_question(question), True


def build_paper(req: GenerateRequest, retrieval: RetrievalResult) -> Paper:
    """Build a complete Paper from retrieval results."""
    num_questions = min(req.total_questions, len(retrieval.items))
    chosen = list(retrieval.items[:num_questions])

    # idx (1-based) → (RevisedQuestion, is_fallback). Keyed by idx so we can
    # both re-order deterministically and pair each result with its own
    # retrieved item — no fragile idx-1 reverse lookup.
    results: dict[int, tuple[RevisedQuestion, bool]] = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        future_to_idx = {
            executor.submit(
                _revise_one,
                retrieved.question,
                req.revision_intensity,
                req.free_text,
            ): idx
            for idx, retrieved in enumerate(chosen, start=1)
        }
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            results[idx] = future.result()

    items: list[PaperItem] = []
    revision_failures: list[int] = []
    for idx, retrieved in enumerate(chosen, start=1):
        rq, is_fallback = results[idx]
        if is_fallback:
            revision_failures.append(idx)
        items.append(
            PaperItem(
                index=idx,
                question=rq,
                source_question_id=retrieved.question.id,
                revision_mode=req.revision_intensity,
            )
        )

    # Actual LLM calls: original makes none; light/fresh call once per question
    # attempted (fallbacks still incurred a call unless the call itself raised,
    # but we report attempts as the observable count — matches Spec B §5.4).
    llm_calls = len(items) if req.revision_intensity != "original" else 0

    return Paper(
        paper_id=uuid.uuid4().hex,
        title=_infer_title(req),
        generated_at=datetime.now(tz.utc),
        request=req,
        items=items,
        metadata={
            "retrieval_warnings": retrieval.warnings,
            "shortfall": retrieval.shortfall,
            "revision_failures": revision_failures,
            "llm_calls": llm_calls,
        },
    )