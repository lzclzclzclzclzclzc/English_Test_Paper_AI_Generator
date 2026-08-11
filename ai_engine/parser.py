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
        "- listening_single_choice: 听力选择",
        "- listening_true_false: 听力判断题（一段长文本/对话后跟多道 True/False 判断题）",
        "- listening_fill_blank: 听力填词（一段听力材料后跟多道小题，每空限填一词，题号连续）",
        "- reading_longtext_single_choice: 阅读理解（一段短文后跟多道 4 选项单选题）",
        "- cloze_single_choice: 完形填空（一段短文含多处空格，每空 4 选项单选）",
        "- reading_first_blank: 阅读首字母填空（一篇短文，内嵌 7 个首字母填空，每空限填一词）",
        "- writing: 英语作文（给出作文题目，由用户写作并由 AI 批改评分）",
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
    valid_question_types = {"single_choice", "word_form", "sentence_rewriting", "listening_single_choice", "listening_true_false", "listening_fill_blank", "reading_longtext_single_choice", "cloze_single_choice", "reading_first_blank", "writing"}

    # Filter invalid KP ids
    valid_kps = []
    for kp_id in response.knowledge_points:
        if kp_id in valid_kp_ids:
            valid_kps.append(kp_id)
        else:
            warnings.append(f"invalid KP id: {kp_id}, dropped")
    response.knowledge_points = valid_kps

    # Filter invalid type_distribution keys (dict[str, int] — pydantic does not
    # validate the key values, so we check them here)
    valid_dist = {}
    for k, v in response.type_distribution.items():
        if k in valid_question_types:
            valid_dist[k] = v
        else:
            warnings.append(f"invalid type_distribution key: {k}, dropped")
    response.type_distribution = valid_dist

    # Cap total_questions
    if response.total_questions > MAX_QUESTIONS:
        warnings.append(f"total_questions capped at {MAX_QUESTIONS}")
        response.total_questions = MAX_QUESTIONS

    # Scale down type_distribution if sum exceeds total_questions
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
) -> GenerateRequest:
    """Parse user's natural language query into GenerateRequest.

    Args:
        user_query: User's natural language request
        mode: Generation mode (fresh/remediation/review)
        wrong_items: List of wrong items for remediation mode
        mastery: Mastery profile for review mode

    Returns:
        Structured GenerateRequest. Caller (pipeline) is responsible for
        setting user_id and review_window_days after this returns.
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

    return validated