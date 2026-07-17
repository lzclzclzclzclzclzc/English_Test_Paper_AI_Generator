"""Parser module: natural language → GenerateRequest.

Converts user's natural language query into structured GenerateRequest.
revision_intensity is inferred by LLM from the user's language.
"""
from __future__ import annotations

import json
from typing import Literal

import sqlite3

from shared.config import get_config
from shared.llm.deepseek import get_llm_client
from shared.schemas import (
    GenerateRequest,
    KnowledgePoint,
    MasteryProfile,
    WrongItemRef,
)
from ai_engine.errors import ParserError
from ai_engine.prompts import load


MAX_QUESTIONS = 30


def _load_kp_catalog(db_path: str) -> list[KnowledgePoint]:
    """Load all knowledge points from SQLite."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute("SELECT id, level1, level2, aliases_json FROM knowledge_points")
        kps = []
        for row in cursor.fetchall():
            aliases = json.loads(row["aliases_json"]) if row["aliases_json"] else []
            kps.append(KnowledgePoint(
                id=row["id"],
                level1=row["level1"],
                level2=row["level2"],
                aliases=aliases,
            ))
        return kps
    finally:
        conn.close()


def _build_kp_catalog_text(kps: list[KnowledgePoint]) -> str:
    """Format KP list for prompt."""
    lines = []
    for kp in kps:
        aliases_str = f" (别名: {', '.join(kp.aliases)})" if kp.aliases else ""
        lines.append(f"- {kp.id}: {kp.level2}{aliases_str}")
    return "\n".join(lines)


def _build_prompt(
    user_query: str,
    mode: Literal["fresh", "remediation", "review"],
    kps: list[KnowledgePoint],
    wrong_items: list[WrongItemRef] | None,
    mastery: MasteryProfile | None,
) -> tuple[str, str]:
    """Build system and user prompts for LLM."""
    kp_catalog = _build_kp_catalog_text(kps)
    
    question_types = "\n".join([
        "- single_choice: 单项选择",
        "- word_form: 词性转换",
        "- sentence_rewriting: 改写句子",
    ])
    
    wrong_items_text = ""
    if wrong_items:
        wrong_items_text = json.dumps([item.model_dump() for item in wrong_items], ensure_ascii=False)
    
    mastery_text = ""
    if mastery:
        mastery_text = json.dumps(mastery.model_dump(), ensure_ascii=False)
    
    system_prompt, user_prompt = load("parser",
        user_query=user_query,
        mode=mode,
        kp_catalog=kp_catalog,
        kp_count=len(kps),
        wrong_items=wrong_items_text if wrong_items else None,
        mastery=mastery_text if mastery else None,
        question_types=question_types,
    )
    
    return system_prompt, user_prompt


def _local_validate(
    response: GenerateRequest,
    kps: list[KnowledgePoint],
) -> tuple[GenerateRequest, list[str]]:
    """Local validation after LLM response.
    
    Filters invalid KP ids, caps question count, adjusts distributions.
    """
    warnings = []
    valid_kp_ids = {kp.id for kp in kps}
    
    valid_kps = []
    for kp_id in response.knowledge_points:
        if kp_id in valid_kp_ids:
            valid_kps.append(kp_id)
        else:
            warnings.append(f"invalid KP id: {kp_id}, dropped")
    response.knowledge_points = valid_kps
    
    if response.total_questions > MAX_QUESTIONS:
        warnings.append(f"total_questions capped at {MAX_QUESTIONS}")
        response.total_questions = MAX_QUESTIONS
    
    total_type_dist = sum(response.type_distribution.values())
    if total_type_dist > response.total_questions:
        scale = response.total_questions / total_type_dist
        response.type_distribution = {
            k: max(1, int(v * scale)) for k, v in response.type_distribution.items()
        }
    
    return response, warnings


def parse(
    user_query: str,
    *,
    mode: Literal["fresh", "remediation", "review"] = "fresh",
    wrong_items: list[WrongItemRef] | None = None,
    mastery: MasteryProfile | None = None,
    user_id: str | None = None,
    review_window_days: int | None = None,
) -> GenerateRequest:
    """Parse user's natural language query into GenerateRequest.
    
    Args:
        user_query: User's natural language request
        mode: Generation mode (fresh/remediation/review)
        wrong_items: List of wrong items for remediation mode
        mastery: Mastery profile for review mode
        user_id: User ID for review mode
        review_window_days: Time window for review mode
    
    Returns:
        Structured GenerateRequest with all fields filled
    """
    cfg = get_config()
    kps = _load_kp_catalog(str(cfg.db_path))
    
    if not kps:
        raise ParserError("No knowledge points found in database")
    
    system_prompt, user_prompt = _build_prompt(user_query, mode, kps, wrong_items, mastery)
    
    llm_client = get_llm_client()
    
    try:
        llm_response = llm_client.structured(
            response_model=GenerateRequest,
            prompt=user_prompt,
            system=system_prompt,
            max_retries=3,
            temperature=0.2,
        )
    except Exception as e:
        raise ParserError(f"LLM call failed: {str(e)}") from e
    
    validated, warnings = _local_validate(llm_response, kps)
    
    validated.mode = mode
    validated.wrong_items = wrong_items or []
    validated.user_id = user_id
    validated.review_window_days = review_window_days
    
    return validated