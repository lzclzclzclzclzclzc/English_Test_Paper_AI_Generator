"""Study-coach agent.

Responsibilities (system prompt):  who the agent is and how it routes.
Learning-plan logic lives in agent/skills/study_plan.py and is exposed to
the coach as a tool via agent.as_tool().
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Disable SDK tracing — we don't have an OpenAI API key for the trace exporter
os.environ.setdefault("OPENAI_AGENTS_DISABLE_TRACING", "1")

from agents import Agent, OpenAIChatCompletionsModel, Runner
from openai import AsyncOpenAI

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.config import get_config
from agent.skills.study_plan import create_study_plan_skill

_COACH_PROMPT = """你是一位中考英语学习助手。

你可以做的事情：
- 制定个性化学习计划（调用"制定学习计划"工具）
- 回答学生关于学习安排的问题

当学生请求制定学习计划时，收集以下信息后调用工具：
- 用户ID（必须）
- 希望制定几天的计划（默认 7 天）
- 是否有特殊要求（可选）

对于其他英语学习问题，直接回答即可。
保持语言亲切，面向初中生。
"""


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
    model = _build_model()
    study_plan_skill = create_study_plan_skill(model)

    return Agent(
        name="中考英语学习助手",
        instructions=_COACH_PROMPT,
        tools=[
            study_plan_skill.as_tool(
                tool_name="制定学习计划",
                tool_description=(
                    "根据用户的历史做题记录制定个性化学习计划，并展示第一天的例题。"
                    "需要提供：用户ID、计划天数、可选的用户要求。"
                ),
            )
        ],
        model=model,
    )


async def ask_coach(user_message: str) -> str:
    agent = create_coach_agent()
    result = await Runner.run(agent, input=user_message)
    return result.final_output
