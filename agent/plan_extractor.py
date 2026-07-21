"""Phase 2: extract structured study plan from natural-language plan text.

Called when the user clicks "一键实施". Takes the Coach's plan output and
returns a validated StudyPlanData object ready for paper generation.

Uses shared/llm/deepseek.py::structured() + instructor for JSON validation
and automatic retry on schema mismatch (max 3 attempts).
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.config import get_config
from shared.llm.deepseek import get_llm_client

QuestionType = Literal["single_choice", "word_form", "sentence_rewriting"]


class StudyPlanDay(BaseModel):
    """一天的练习安排 = 一个出题需求（可含多个知识点/题型，对应 GenerateRequest）。"""
    index: int = Field(ge=1, description="第几天，从 1 开始")
    theme: str = Field(default="", description="当天主题，如'名词专题'")
    knowledge_points: list[str] = Field(
        description="当天要练的知识点 id 列表，必须全部来自合法清单，至少一个"
    )
    question_types: list[QuestionType] = Field(
        description="当天涉及的题型列表（与所选知识点的题型对应）"
    )
    total_questions: int = Field(ge=1, le=20, description="当天总题量")
    note: str = Field(default="", description="备注，如'严重薄弱，重点练习'")


class StudyPlanData(BaseModel):
    user_id: str
    total_days: int = Field(ge=1)
    days: list[StudyPlanDay]


def _load_valid_kp_ids() -> dict[str, str]:
    """Load all KP ids from the question bank. Returns {id: level2_name}."""
    db_path = str(get_config().db_path)
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT id, level2 FROM knowledge_points ORDER BY id").fetchall()
        return {r[0]: r[1] for r in rows}
    finally:
        conn.close()


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
        ValueError: if extracted KP ids are not in the question bank
        Exception: if LLM fails after 3 retries
    """
    client = get_llm_client()
    valid_kps = _load_valid_kp_ids()

    kp_catalog = "\n".join(f"- {kp_id}: {name}" for kp_id, name in valid_kps.items())

    system = f"""你是一个信息提取专家。
从用户提供的中考英语学习计划文本中，提取结构化的每日安排数据。

## 合法知识点 id 清单（knowledge_points 只能从以下选取）
{kp_catalog}

## 提取规则
- 每一天是一个条目：包含 theme（当天主题）、knowledge_points（当天要练的知识点 id 列表）、
  question_types（涉及的题型列表）、total_questions（当天总题量）、note（备注）
- **一天可以有多个知识点**：原文里"第X天：名词专题（名词变复数、名词→动词…）"这类
  一天多考点的安排，要把每个考点的 id 都提取进 knowledge_points 列表，不能只保留一个
- knowledge_points 里的 id 必须从上方清单中选择，不能编造或缩写；找不到完全匹配就选语义最接近的
- question_types 是这些知识点对应的题型集合（single_choice / word_form / sentence_rewriting）
- total_questions 取原文当天的总题量（各考点题量之和，1~20）
- note 从原文中提取该天的备注描述
"""

    prompt = f"""以下是一份学习计划文本，请提取每日安排：

用户ID：{user_id}

---
{plan_text}
---

请提取所有天的安排，注意把每天的多个知识点都完整放进 knowledge_points 列表。"""

    result: StudyPlanData = client.structured(
        response_model=StudyPlanData,
        prompt=prompt,
        system=system,
        max_retries=3,
        temperature=0.1,
    )

    # Override user_id with the session value
    result.user_id = user_id

    # Local validation: reject any KP id not in the bank
    invalid = [
        kp
        for day in result.days
        for kp in day.knowledge_points
        if kp not in valid_kps
    ]
    if invalid:
        raise ValueError(
            f"plan_extractor returned invalid KP ids (not in question bank): {invalid}"
        )

    # Attach dates to notes if start_date provided
    if start_date:
        for day in result.days:
            day_date = start_date + timedelta(days=day.index - 1)
            date_str = day_date.strftime("%Y-%m-%d")
            day.note = f"{date_str} {day.note}".strip()

    return result
