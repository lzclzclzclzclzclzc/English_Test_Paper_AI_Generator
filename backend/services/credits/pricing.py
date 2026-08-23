"""积分价目表 —— 全站唯一事实来源（docs/credits-design.md §3）。

前端不硬编码价格：`GET /api/credits/prices` 把这张表下发，CTA 旁的「≈ N 积分」
和余额不足判断都按它算。改价只改这里。

价格单位：积分（1 积分 ≈ ¥0.01，见 packs.py）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Action = Literal[
    "generate_original",
    "generate_light",
    "generate_fresh",
    "revise_paper",
    "solution",
    "writing_grade",
    "agent_message",
]


@dataclass(frozen=True)
class Price:
    action: str
    label: str
    base: int          # 每次固定费用
    per_unit: int      # 每题 / 每篇 的叠加费用（0 = 按次计价）
    unit: str          # 叠加单位名（"题" / "篇" / ""）
    note: str


PRICES: dict[str, Price] = {
    "generate_original": Price("generate_original", "出卷 · 真题原样", 5, 1, "题", "只做意图解析，1 次 LLM"),
    "generate_light": Price("generate_light", "出卷 · AI 改编", 5, 3, "题", "每题 1 次 LLM 改写"),
    "generate_fresh": Price("generate_fresh", "出卷 · 全新出题", 5, 4, "题", "每题 1 次 LLM 命题（含复习卷 / 巩固卷 / 主题出卷）"),
    "revise_paper": Price("revise_paper", "一句话重新出卷", 5, 4, "题", "整卷重跑解析 + 改写"),
    "solution": Price("solution", "AI 单题讲解", 5, 0, "", "每次 1 次 LLM"),
    "writing_grade": Price("writing_grade", "作文批改", 20, 0, "", "每篇 1 次 LLM 三维批改"),
    "agent_message": Price("agent_message", "学习助手 · 每条消息", 2, 0, "", "助手里触发的出卷按出卷价另计"),
}

# 出卷改题强度 → 计价动作
INTENSITY_ACTION: dict[str, str] = {
    "original": "generate_original",
    "light": "generate_light",
    "fresh": "generate_fresh",
}


def price(action: str, units: int = 0) -> int:
    """`units` = 题数 / 篇数；按次计价的动作忽略它。未知动作视为免费（0）。"""
    p = PRICES.get(action)
    if p is None:
        return 0
    return p.base + p.per_unit * max(0, units)


def price_table() -> list[dict]:
    return [
        {
            "action": p.action,
            "label": p.label,
            "base": p.base,
            "per_unit": p.per_unit,
            "unit": p.unit,
            "note": p.note,
        }
        for p in PRICES.values()
    ]
