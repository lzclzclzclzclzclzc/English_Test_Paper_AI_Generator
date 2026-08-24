"""LLM-generated example sentence for a single vocabulary word.

Kept deliberately small: the study UI shows a "生成例句" button that calls
this once per click (charged 1 credit server-side). Structured output so the
English sentence and its Chinese translation come back cleanly separated.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from shared.llm.deepseek import get_llm_client

_SYSTEM = "你是一位中考英语老师，为初中生编写简洁、地道的例句。"


class VocabularyExample(BaseModel):
    example_en: str = Field(description="一个使用该单词的英文例句，自然地道，长度约 8-16 词，难度贴近中考")
    example_zh: str = Field(description="该英文例句通顺的中文翻译")


def generate_example(term: str, part_of_speech: str, meanings: list[str]) -> VocabularyExample:
    """Generate one exam-appropriate example sentence (+ Chinese translation) for a word."""
    meaning_text = "；".join(m for m in meanings if m.strip()) or "（无释义）"
    prompt = (
        f"为下面这个英语单词写一个适合中考初中生的例句。\n"
        f"单词：{term}\n"
        f"词性：{part_of_speech}\n"
        f"释义：{meaning_text}\n\n"
        f"要求：\n"
        f"- 例句必须真正用到「{term}」（可使用其正确的时态 / 单复数 / 词形变化）。\n"
        f"- 句子自然、地道，长度约 8-16 个词，难度贴近中考。\n"
        f"- 再给出这句话通顺的中文翻译。"
    )
    return get_llm_client().structured(
        response_model=VocabularyExample,
        prompt=prompt,
        system=_SYSTEM,
        temperature=0.5,
    )
