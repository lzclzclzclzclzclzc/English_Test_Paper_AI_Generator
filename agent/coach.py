"""Study-coach agent.

Single-agent design: Coach loads skill instructions from markdown files
on startup and injects them into the system prompt. No sub-agents.
Coach directly calls get_user_history and get_example_questions tools.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("OPENAI_AGENTS_DISABLE_TRACING", "1")

from agents import Agent, OpenAIChatCompletionsModel
from openai import AsyncOpenAI

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.config import get_config
from agent.tools import get_example_questions, get_user_history

_SKILLS_DIR = Path(__file__).parent / "skills"

_COACH_BASE_PROMPT = """你是一位中考英语学习助手。

你可以做的事情：
- 制定个性化学习计划（按照下方 skill 指令执行）
- 查找某个知识点的例题（调用 get_example_questions 工具）
- 回答学生关于学习安排的问题

## 重要规则

**严禁自己编造题目**：当学生要求查例题时，
必须调用 get_example_questions 工具从题库获取，不能凭自己的知识生成题目。
如果工具返回为空，告知学生该知识点暂无例题。

保持语言亲切，面向初中生。

---

{skills}
"""


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
        skills=skills_content if skills_content else "（暂无已加载的 skill）"
    )

    return Agent(
        name="中考英语学习助手",
        instructions=system_prompt,
        tools=[get_user_history, get_example_questions],
        model=_build_model(),
    )
