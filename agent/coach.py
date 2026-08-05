"""Study-coach agent.

Single-agent design: Coach loads skill instructions from markdown files
on startup and injects them into the system prompt. No sub-agents.
Coach directly calls get_user_history and get_example_questions tools.
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

os.environ.setdefault("OPENAI_AGENTS_DISABLE_TRACING", "1")

from agents import Agent, OpenAIChatCompletionsModel
from openai import AsyncOpenAI

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.config import get_config
from agent.tools import get_example_questions, get_user_history, generate_paper, implement_study_plan

_SKILLS_DIR = Path(__file__).parent / "skills"

_COACH_BASE_PROMPT = """你是一位中考英语学习助手。

你可以做的事情：
- 根据用户的自然语言请求出题（调用 generate_paper 工具，按照出题 skill 指令执行）
- 制定个性化学习计划（按照学习计划 skill 指令执行）
- 查找某个知识点的例题（调用 get_example_questions 工具）
- 回答学生关于学习安排的问题

## 重要规则

**严禁自己编造题目**：当学生要求查例题或看题目时，
必须调用工具从题库获取，不能凭自己的知识生成题目。
如果工具返回为空，告知学生该知识点暂无题目。

**只能使用下方"题库知识点清单"中真实存在的知识点**：
出题、制定学习计划、推荐练习时，只能选用清单里列出的知识点，
严禁编造清单中没有的考点（例如"名词所有格""综合词性转换"若不在清单里就不能用）。
每个知识点属于某一种题型（单项选择 / 词形转换 / 改写句子 / 听力选择），
安排练习时题型必须与该知识点所属的题型一致，否则会出卷失败。
制定学习计划时，只从清单里挑选知识点排入每日安排。

保持语言亲切，面向初中生。

---

{kp_catalog}

---

{skills}
"""


def _load_kp_catalog() -> str:
    """Load the real KP catalog grouped by question type (level1), so the
    agent only ever plans/generates against knowledge points that actually
    exist in the bank — with the correct question type for each."""
    type_names = {
        "single_choice": "单项选择",
        "word_form": "词形转换",
        "sentence_rewriting": "改写句子",
        "listening_single_choice": "听力选择",
    }
    db_path = str(get_config().db_path)
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT id, level1, level2 FROM knowledge_points ORDER BY level1, level2"
        ).fetchall()
    except sqlite3.Error:
        return "## 题库知识点清单\n（暂时无法读取知识点清单）"
    finally:
        conn.close()

    if not rows:
        return "## 题库知识点清单\n（题库暂无知识点）"

    grouped: dict[str, list[tuple[str, str]]] = {}
    for kp_id, level1, level2 in rows:
        grouped.setdefault(level1, []).append((kp_id, level2))

    lines = [
        "## 题库知识点清单",
        "以下是题库中真实存在的全部知识点，按题型分组。"
        "出题 / 学习计划只能从这里选，且题型必须与所属分组一致：",
        "",
    ]
    for level1, kps in grouped.items():
        lines.append(f"### {type_names.get(level1, level1)}（question_type = {level1}）")
        for kp_id, level2 in kps:
            lines.append(f"- {level2}（{kp_id}）")
        lines.append("")
    return "\n".join(lines).strip()


def _load_skills() -> str:
    """Load all skill markdown files from the skills/ directory."""
    parts = []
    for md_file in sorted(_SKILLS_DIR.glob("*.md")):
        content = md_file.read_text(encoding="utf-8").strip()
        parts.append(content)
    return "\n\n---\n\n".join(parts) if parts else ""


def _build_model() -> OpenAIChatCompletionsModel:
    cfg = get_config()
    client = AsyncOpenAI(
        api_key=cfg.llm_api_key,
        base_url=cfg.llm_base_url,
    )
    return OpenAIChatCompletionsModel(
        model=cfg.llm_model,
        openai_client=client,
    )


def create_coach_agent() -> Agent:
    skills_content = _load_skills()
    system_prompt = _COACH_BASE_PROMPT.format(
        kp_catalog=_load_kp_catalog(),
        skills=skills_content if skills_content else "（暂无已加载的 skill）",
    )

    return Agent(
        name="中考英语学习助手",
        instructions=system_prompt,
        tools=[get_user_history, get_example_questions, generate_paper, implement_study_plan],
        model=_build_model(),
    )
