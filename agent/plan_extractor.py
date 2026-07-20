"""Phase 2: extract structured study plan from natural-language plan text.

Called when the user clicks "一键实施". Takes the Coach's plan output and
returns a validated StudyPlanData object ready for paper generation.

Uses shared/llm/deepseek.py::structured() + instructor for JSON validation
and automatic retry on schema mismatch (max 3 attempts).
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.llm.deepseek import get_llm_client

QuestionType = Literal["single_choice", "word_form", "sentence_rewriting"]


class StudyPlanDay(BaseModel):
    index: int = Field(ge=1, description="第几天，从 1 开始")
    knowledge_point_id: str = Field(description="知识点 id，必须是 kp_ 开头的真实 id")
    kp_name: str = Field(description="知识点中文名")
    question_type: QuestionType = Field(description="题型")
    count: int = Field(ge=8, le=10, description="建议练习题数，8~10 之间")
    note: str = Field(default="", description="备注，如'严重薄弱，重点练习'")


class StudyPlanData(BaseModel):
    user_id: str
    total_days: int = Field(ge=1)
    days: list[StudyPlanDay]


_EXTRACT_SYSTEM = """你是一个信息提取专家。
从用户提供的中考英语学习计划文本中，提取结构化的每日安排数据。

提取规则：
- knowledge_point_id 必须是原文中出现的真实 KP id（格式为 kp_xxx），不能编造
- question_type 只能是 single_choice / word_form / sentence_rewriting 之一，根据原文的题型描述判断
- count 取原文建议练习题数，若不在 8~10 范围内则取最近的边界值
- 每天作为一个独立条目，不要合并或跳过
- note 从原文中提取该天的备注描述（如"严重薄弱"、"巩固复习"等）
"""


def extract_study_plan(
    plan_text: str,
    user_id: str,
    start_date: date | None = None,
) -> StudyPlanData:
    """Extract structured plan from natural-language text.

    Args:
        plan_text: Coach's full output (natural language plan)
        user_id: injected from session (not from plan text)
        start_date: if provided, used to compute per-day dates (stored in note)

    Returns:
        Validated StudyPlanData, with instructor retry on schema errors.

    Raises:
        Exception: if LLM fails after 3 retries
    """
    client = get_llm_client()

    prompt = f"""以下是一份学习计划文本，请提取每日安排：

用户ID：{user_id}

---
{plan_text}
---

请提取所有天的安排，knowledge_point_id 必须与原文中的 KP id 完全一致。"""

    result: StudyPlanData = client.structured(
        response_model=StudyPlanData,
        prompt=prompt,
        system=_EXTRACT_SYSTEM,
        max_retries=3,
        temperature=0.1,
    )

    # Override user_id with the session value (don't trust LLM-extracted one)
    result.user_id = user_id

    # Attach dates to notes if start_date provided
    if start_date:
        for day in result.days:
            day_date = start_date + timedelta(days=day.index - 1)
            date_str = day_date.strftime("%Y-%m-%d")
            day.note = f"{date_str} {day.note}".strip()

    return result
