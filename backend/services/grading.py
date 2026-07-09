from __future__ import annotations

import re


def normalize(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"[.!?,;:]+$", "", value)
    return value


def compare(user_answer: str, correct_answer: str, question_type: str) -> bool:
    if question_type == "single_choice":
        return user_answer.strip().upper() == correct_answer.strip().upper()
    return normalize(user_answer) == normalize(correct_answer)
