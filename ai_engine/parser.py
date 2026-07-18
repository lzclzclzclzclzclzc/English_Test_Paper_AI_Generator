"""Natural-language request to validated generation request."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ai_engine.errors import ParserError
from shared import storage
from shared.schemas import GenerateRequest, KnowledgePoint, MasteryProfile, RevisionMode, WrongItemRef

MAX_QUESTIONS = 30


class ParserResponse(BaseModel):
    total_questions: int = 3
    knowledge_points: list[str] = Field(default_factory=list)
    question_types: list[Literal["single_choice", "word_form", "sentence_rewriting"]] = Field(default_factory=list)
    type_distribution: dict[str, int] = Field(default_factory=dict)
    revision_intensity: RevisionMode = "light"
    free_text: str = ""


def _catalog_text(kps: list[KnowledgePoint]) -> str:
    return "\n".join(f"- {kp.id}: {kp.level1}/{kp.level2}" for kp in kps)


def parse(
    user_query: str, *, mode: Literal["fresh", "remediation", "review"] = "fresh",
    wrong_items: list[WrongItemRef] | None = None, mastery: MasteryProfile | None = None,
    user_id: str | None = None, review_window_days: int | None = None,
) -> GenerateRequest:
    kps = storage.list_knowledge_points()
    if not kps:
        raise ParserError("No knowledge points found in database")
    context: list[str] = [
        "You convert a Chinese English-exam request into JSON.",
        "Choose revision_intensity: original for explicit original exam questions; fresh for explicit new/original scenarios; otherwise light.",
        "free_text contains only an unstructured semantic scenario; leave it empty for ordinary quota/KP requests.",
        "Allowed knowledge points:\n" + _catalog_text(kps),
        "Request: " + user_query,
        "Mode: " + mode,
    ]
    if wrong_items:
        context.append("Wrong items: " + str([x.model_dump() for x in wrong_items]))
    if mastery:
        context.append("Mastery: " + str(mastery.model_dump()))
    try:
        from shared.llm.deepseek import get_llm_client
        response = get_llm_client().structured(
            response_model=ParserResponse, prompt="\n\n".join(context), max_retries=3,
        )
    except Exception as exc:
        raise ParserError(f"LLM parser failed: {exc}") from exc
    valid_ids = {kp.id for kp in kps}
    valid_types = {"single_choice", "word_form", "sentence_rewriting"}
    count = max(1, min(MAX_QUESTIONS, response.total_questions))
    distribution = {key: max(0, value) for key, value in response.type_distribution.items() if key in valid_types and value > 0}
    if sum(distribution.values()) > count:
        distribution = {}
    return GenerateRequest(
        mode=mode, knowledge_points=[kp for kp in response.knowledge_points if kp in valid_ids],
        question_types=response.question_types, total_questions=count, total_score=count * 5,
        type_distribution=distribution, revision_intensity=response.revision_intensity,
        wrong_items=wrong_items or [], user_id=user_id, review_window_days=review_window_days,
        free_text=response.free_text.strip(),
    )
