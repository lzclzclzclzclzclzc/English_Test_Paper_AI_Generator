from __future__ import annotations

import re

from backend.schemas import UserAnswerValue
from shared.schemas import Answer


def normalize(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"[.!?,;:]+$", "", value)
    return value


def compare(user_answer: UserAnswerValue, correct_answer: Answer, question_type: str) -> bool:
    """Compare a submitted answer with the stored answer_json-compatible value."""
    if isinstance(correct_answer, list):
        return _compare_blank_answers(user_answer, correct_answer)
    if question_type in {"single_choice", "listening_single_choice", "listening_true_false", "reading_longtext_single_choice", "cloze_single_choice"}:
        return isinstance(user_answer, str) and user_answer.strip().upper() == correct_answer.strip().upper()
    return normalize(str(user_answer)) == normalize(correct_answer)


def _compare_blank_answers(user_answer: UserAnswerValue, correct_answers: list[dict[str, list[str]]]) -> bool:
    normalized_user = _user_answer_to_blanks(user_answer)
    if not normalized_user:
        return False
    for candidate in correct_answers:
        normalized_candidate = {
            key: {normalize(option) for option in options}
            for key, options in candidate.items()
        }
        if set(normalized_user) != set(normalized_candidate):
            continue
        if all(normalized_user[key] in normalized_candidate[key] for key in normalized_candidate):
            return True
    return False


def _user_answer_to_blanks(user_answer: UserAnswerValue) -> dict[str, str]:
    if isinstance(user_answer, dict):
        return {key: normalize(value) for key, value in user_answer.items() if value.strip()}
    if isinstance(user_answer, list):
        return {f"blank{index}": normalize(value) for index, value in enumerate(user_answer, start=1) if value.strip()}
    normalized = normalize(user_answer)
    return {"blank1": normalized} if normalized else {}
