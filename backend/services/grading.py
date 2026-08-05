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
    """Compare a submitted answer with the stored answer_json-compatible value.

    Fill-in answer types (word_form / sentence_rewriting / listening_fill_blank /
    reading_first_blank) store `answer` as a list[BlankGroup] and are graded by
    `_compare_blank_answers` — blank-by-blank, any candidate in a group hits.
    """
    if isinstance(correct_answer, list):
        return _compare_blank_answers(user_answer, correct_answer)
    if question_type in {"single_choice", "listening_single_choice", "listening_true_false", "reading_longtext_single_choice", "cloze_single_choice"}:
        return isinstance(user_answer, str) and user_answer.strip().upper() == correct_answer.strip().upper()
    return normalize(str(user_answer)) == normalize(correct_answer)


def _compare_blank_answers(user_answer: UserAnswerValue, correct_answers: list[dict[str, list[str]]]) -> bool:
    normalized_user = _user_answer_to_blanks(user_answer)
    if not normalized_user:
        return False
    candidates = _normalize_candidates(correct_answers)
    for candidate in candidates:
        normalized_candidate = {
            key: {normalize(option) for option in options}
            for key, options in candidate.items()
        }
        if set(normalized_user) != set(normalized_candidate):
            continue
        if all(normalized_user[key] in normalized_candidate[key] for key in normalized_candidate):
            return True
    return False


def _normalize_candidates(correct_answers: list[dict[str, list[str]]]) -> list[dict[str, list[str]]]:
    """把"多元素单空 dict"（阅读首字母填空 [{blank1},{blank2},…]）合并为单个整体候选。

    阅读首字母填空的 answer 是每个空一个 dict（各只有 1 个键），语义是"所有空必须
    一起正确"，而非"多个可替换的候选组合"。若不加合并，逐候选比对时用户答满 7 空的
    键集合永远不等于单键候选，整道题恒判错。合并后，只要任意一空错误即整题错误。
    其它题型（word_form / sentence_rewriting / listening_fill_blank）的候选元素
    含多个键（或本身就是单元素），保持原样。
    """
    if correct_answers and all(isinstance(c, dict) and len(c) == 1 for c in correct_answers):
        merged: dict[str, list[str]] = {}
        for c in correct_answers:
            merged.update(c)
        return [merged]
    return correct_answers


def _user_answer_to_blanks(user_answer: UserAnswerValue) -> dict[str, str]:
    if isinstance(user_answer, dict):
        return {key: normalize(value) for key, value in user_answer.items() if value.strip()}
    if isinstance(user_answer, list):
        return {f"blank{index}": normalize(value) for index, value in enumerate(user_answer, start=1) if value.strip()}
    normalized = normalize(user_answer)
    return {"blank1": normalized} if normalized else {}
