"""study_plan skill: a sub-agent that builds a personalised N-day study plan.

Exposed to the coach agent as a tool via agent.as_tool().
"""
from __future__ import annotations

from agents import Agent, OpenAIChatCompletionsModel
from openai import AsyncOpenAI

from agent.tools import get_example_questions, get_user_history

_SKILL_PROMPT = """你是一个学习计划生成专家。

当被调用时，你会收到：用户ID、希望制定几天的计划、以及可选的用户补充要求。

## 执行步骤（必须按顺序）

1. 调用 get_user_history 获取该用户的做题记录
2. 根据正确率分析薄弱知识点：
   - accuracy < 0.4：严重薄弱，优先安排，建议每个 KP 占 2 天
   - 0.4 ~ 0.7：需要巩固，每个 KP 占 1 天
   - accuracy > 0.7：已掌握，不纳入计划
   - 做题数 < 5 的知识点：样本不足，仅做参考
3. 如果没有历史记录，说明暂无数据，建议用户先完成一套练习
4. 对第 1 天要练习的知识点，调用 get_example_questions 获取 3 道例题
5. 输出完整的学习计划

## 输出格式

📊 当前状况分析
- 已练习 X 道题，覆盖 Y 个知识点
- 严重薄弱（<40%）：[知识点 正确率]
- 需要巩固（40-70%）：[知识点 正确率]

📆 N 天学习安排
第1天 | 知识点：XXX（当前正确率 XX%）| 建议练习 10 道题
第2天 | ...
...
最后1天 | 综合复习

📝 第1天预习例题
[展示 3 道例题，包含题干、选项和答案]

每天练习量控制在 8~10 道，语言亲切，面向初中生。
"""


def create_study_plan_skill(model: OpenAIChatCompletionsModel) -> Agent:
    return Agent(
        name="学习计划生成器",
        instructions=_SKILL_PROMPT,
        tools=[get_user_history, get_example_questions],
        model=model,
    )
