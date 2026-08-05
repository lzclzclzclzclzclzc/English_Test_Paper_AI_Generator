from __future__ import annotations

from backend.services.grading import compare


def test_single_choice_is_case_insensitive_string_only():
    assert compare("b", "B", "single_choice") is True
    assert compare(" B ", "B", "single_choice") is True
    assert compare(["B"], "B", "single_choice") is False


def test_single_blank_accepts_string_answer():
    correct = [{"blank1": ["written"]}]
    assert compare(" Written. ", correct, "word_form") is True
    assert compare("writing", correct, "word_form") is False


def test_multi_blank_accepts_ordered_list_answer():
    correct = [{"blank1": ["so"], "blank2": ["that"]}]
    assert compare([" so ", "that."], correct, "sentence_rewriting") is True
    assert compare(["that", "so"], correct, "sentence_rewriting") is False


def test_multi_blank_accepts_named_blank_answer():
    correct = [{"blank1": ["haven't"], "blank2": ["yet"]}]
    assert compare({"blank1": " Haven't ", "blank2": "yet."}, correct, "sentence_rewriting") is True
    assert compare({"blank1": "haven't"}, correct, "sentence_rewriting") is False


def test_multiple_candidate_combinations_and_synonyms():
    correct = [
        {"blank1": ["in"], "blank2": ["order"]},
        {"blank1": ["so"], "blank2": ["as"]},
    ]
    assert compare(["so", "as"], correct, "sentence_rewriting") is True
    assert compare(["in", "order"], correct, "sentence_rewriting") is True
    assert compare(["in", "as"], correct, "sentence_rewriting") is False


def test_empty_blank_answer_is_wrong():
    correct = [{"blank1": ["proofs"]}]
    assert compare("", correct, "word_form") is False
    assert compare({"blank1": ""}, correct, "word_form") is False


def test_reading_first_blank_all_blanks_must_be_correct():
    """阅读首字母填空：answer 是多个单空 dict，必须全部正确才算对，任一空错即整题错。"""
    correct = [
        {"blank1": ["aware"]},
        {"blank2": ["advantages"]},
        {"blank3": ["Therefore"]},
    ]
    all_correct = {
        "blank1": "aware",
        "blank2": "advantages",
        "blank3": "Therefore",
    }
    one_wrong = dict(all_correct)
    one_wrong["blank2"] = "wrong"
    only_one_ok = {k: ("aware" if k == "blank1" else "wrong") for k in all_correct}

    assert compare(all_correct, correct, "reading_first_blank") is True
    assert compare(one_wrong, correct, "reading_first_blank") is False
    assert compare(only_one_ok, correct, "reading_first_blank") is False
    assert compare({}, correct, "reading_first_blank") is False
