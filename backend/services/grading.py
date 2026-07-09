from __future__ import annotations

import re

from shared.schemas import AnswerValue, UserAnswerValue


def normalize(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"[.!?,;:]+$", "", value)
    return value


def compare(user_answer: UserAnswerValue, correct_answer: AnswerValue, question_type: str) -> bool:
    if isinstance(correct_answer, list):
        return _compare_blank_answers(user_answer, correct_answer)
    if question_type == "single_choice":
        return str(user_answer).strip().upper() == correct_answer.strip().upper()
    return normalize(str(user_answer)) == normalize(correct_answer)


def _compare_blank_answers(user_answer: UserAnswerValue, correct_answers: list[dict[str, list[str]]]) -> bool:
    normalized_user = _user_answer_to_blanks(user_answer)
    for candidate in correct_answers:
        if set(normalized_user) != set(candidate):
            continue
        if all(normalized_user[key] in {normalize(option) for option in options} for key, options in candidate.items()):
            return True
    return False


def _user_answer_to_blanks(user_answer: UserAnswerValue) -> dict[str, str]:
    if isinstance(user_answer, dict):
        return {key: normalize(value) for key, value in user_answer.items()}
    if isinstance(user_answer, list):
        return {f"blank{index}": normalize(value) for index, value in enumerate(user_answer, start=1)}
    return {"blank1": normalize(user_answer)}
