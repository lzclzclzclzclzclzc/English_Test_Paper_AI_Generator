"""Unit tests for ingestion.chapter_splitter.

Contract:
- Three question types parsed from `# 1 单项选择` / `# 3 词性转换` / `# 4 改写句子`
- Half- and full-width parens/dashes/periods handled
- 【同考点汇总】 variants keep their "N-K" numbering (recoverable by callers)
- Answer page indexed by (qtype, chapter_l2, number)
- Missing options → discard (no_options), never crash
- 连词成句 (scramble) accepted without a template paragraph
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from ingestion.chapter_splitter import (
    RawQuestion,
    parse_answer_page,
    split_book,
    write_split_result,
)


def _write_book(tmp_path: Path, files: dict[str, str]) -> Path:
    """Materialize the four expected md files under a per-book dir."""
    book_dir = tmp_path / "book"
    book_dir.mkdir()
    for name, content in files.items():
        (book_dir / name).write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
    return book_dir


# ─────────────────────────────────────────────────────────────────────────────
# single_choice
# ─────────────────────────────────────────────────────────────────────────────
def test_single_choice_halfwidth(tmp_path: Path) -> None:
    """Yimo-style: half-width parens, options on one line."""
    book_dir = _write_book(tmp_path, {
        "单项选择.md": """
            # 1 单项选择

            ## 1.1 语音

            ( )1.(2020·宝山·一模)Which word is pronounced /heɪt/?

            A.height B.hate C.hurt D.heart
        """,
        "词性转换.md": "# 3 词性转换\n\n## 3.1 复数\n",
        "改写句子.md": "# 4 改写句子\n\n## 4.1 否定\n",
        "参考答案.md": """
            # 参考答案

            1 单项选择

            1.1 语音

            1.B
        """,
    })
    result = split_book(book_dir, book_slug="t")
    assert len(result.questions) == 1
    q = result.questions[0]
    assert q.question_type == "single_choice"
    assert q.chapter_l1 == "1 单项选择"
    assert q.chapter_l2 == "1.1 语音"
    assert q.number == "1"
    assert "-" not in q.number                                 # main-line question
    assert q.stem == "Which word is pronounced /heɪt/?"
    assert q.options is not None
    assert [o.label for o in q.options] == ["A", "B", "C", "D"]
    assert q.options[1].text == "hate"
    assert q.answer == "B"


def test_single_choice_fullwidth_multiparagraph_options(tmp_path: Path) -> None:
    """Ermo-style: full-width parens, and each option on its own paragraph."""
    book_dir = _write_book(tmp_path, {
        "单项选择.md": """
            # 1 单项选择

            ## 1.1 语音

            （ ）5.（2020·黄浦·二模）Which sentence is correct?

            A.Let's add some sugar in the bottle.

            B.Look both ways before you cross the street.

            C.Bob arrived at the bottom of the hill.

            D.I met Jane's boss at a dinner party yesterday.
        """,
        "词性转换.md": "# 3 词性转换\n\n## 3.1 复数\n",
        "改写句子.md": "# 4 改写句子\n\n## 4.1 否定\n",
        "参考答案.md": """
            # 参考答案

            1 单项选择

            1.1 语音

            5.B
        """,
    })
    result = split_book(book_dir, book_slug="t")
    assert len(result.questions) == 1
    q = result.questions[0]
    assert q.options is not None
    assert len(q.options) == 4
    assert q.options[0].text == "Let's add some sugar in the bottle."
    assert q.answer == "B"


def test_single_choice_missing_options_discarded(tmp_path: Path) -> None:
    """Image-based option questions (options lost when ignore_images=True)
    must be discarded with `no_options`, never emitted with a malformed
    options list."""
    book_dir = _write_book(tmp_path, {
        "单项选择.md": """
            # 1 单项选择

            ## 1.1 语音

            ( )6.(2020·嘉定·一模)Which underlined part is different?

            ( )7.(2020·静安·一模)Which word is pronounced as /haɪt/?

            A.heart B.hunt C.hate D.height
        """,
        "词性转换.md": "# 3 词性转换\n\n## 3.1 复数\n",
        "改写句子.md": "# 4 改写句子\n\n## 4.1 否定\n",
        "参考答案.md": """
            # 参考答案

            1 单项选择

            1.1 语音

            6.D 7.C
        """,
    })
    result = split_book(book_dir, book_slug="t")
    assert len(result.questions) == 1                          # only q7 survives
    assert result.questions[0].number == "7"
    assert result.stats.discarded == {"single_choice:no_options": 1}


# ─────────────────────────────────────────────────────────────────────────────
# variant handling
# ─────────────────────────────────────────────────────────────────────────────
def test_variant_marker_fullwidth_dash(tmp_path: Path) -> None:
    """【同考点汇总】 followed by full-width dash numbering (ermo)."""
    book_dir = _write_book(tmp_path, {
        "单项选择.md": """
            # 1 单项选择

            ## 1.1 语音

            （ ）11.（2020·青浦·二模）Which underlined part is different?

            A.factory B.painted C.jumped D.asked

            【同考点汇总】

            （ ）11－1.（2020·长宁·二模）Which underlined part is different?

            A.rain B.chain C.captain D.mail
        """,
        "词性转换.md": "# 3 词性转换\n\n## 3.1 复数\n",
        "改写句子.md": "# 4 改写句子\n\n## 4.1 否定\n",
        "参考答案.md": """
            # 参考答案

            1 单项选择

            1.1 语音

            11.B

            【同考点汇总】

            11－1.C
        """,
    })
    result = split_book(book_dir, book_slug="t")
    numbers = sorted(q.number for q in result.questions)
    assert numbers == ["11", "11-1"]                          # dash normalized
    variant = next(q for q in result.questions if "-" in q.number)
    assert variant.number == "11-1"
    assert variant.answer == "C"


# ─────────────────────────────────────────────────────────────────────────────
# word_form
# ─────────────────────────────────────────────────────────────────────────────
def test_word_form_basic(tmp_path: Path) -> None:
    book_dir = _write_book(tmp_path, {
        "单项选择.md": "# 1 单项选择\n\n## 1.1 语音\n",
        "词性转换.md": """
            # 3 词性转换

            ## 3.1 名词改复数

            1.(2020·宝山·一模)Scientists are trying to find more________for their argument.(proof)
        """,
        "改写句子.md": "# 4 改写句子\n\n## 4.1 否定\n",
        "参考答案.md": """
            # 参考答案

            3 词性转换

            3.1 名词改复数

            1.proofs
        """,
    })
    result = split_book(book_dir, book_slug="t")
    assert len(result.questions) == 1
    q = result.questions[0]
    assert q.question_type == "word_form"
    assert q.hint == "proof"
    assert q.answer == "proofs"
    assert q.options is None
    assert "________" in q.stem


def test_word_form_midline_hint(tmp_path: Path) -> None:
    """Hint mid-line (yimo 3.13/1). The last parenthesised English word wins."""
    book_dir = _write_book(tmp_path, {
        "单项选择.md": "# 1 单项选择\n\n## 1.1 语音\n",
        "词性转换.md": """
            # 3 词性转换

            ## 3.13 形容词/副词等级

            1.(2020·奉贤·一模)—Which bird is the________in the world?(loud)—It might be the male white bell bird.
        """,
        "改写句子.md": "# 4 改写句子\n\n## 4.1 否定\n",
        "参考答案.md": """
            # 参考答案

            3 词性转换

            3.13 形容词/副词等级

            1.loudest
        """,
    })
    result = split_book(book_dir, book_slug="t")
    assert len(result.questions) == 1
    assert result.questions[0].hint == "loud"
    assert result.questions[0].answer == "loudest"


# ─────────────────────────────────────────────────────────────────────────────
# sentence_rewriting
# ─────────────────────────────────────────────────────────────────────────────
def test_sentence_rewriting_two_paragraph(tmp_path: Path) -> None:
    book_dir = _write_book(tmp_path, {
        "单项选择.md": "# 1 单项选择\n\n## 1.1 语音\n",
        "词性转换.md": "# 3 词性转换\n\n## 3.1 复数\n",
        "改写句子.md": """
            # 4 改写句子

            ## 4.1 改为否定句

            1.(2020·宝山·一模)This helicopter cost me 240 yuan.(改为否定句)

            This helicopter________________me 240 yuan.
        """,
        "参考答案.md": """
            # 参考答案

            4 改写句子

            4.1 改为否定句

            1.didn't cost
        """,
    })
    result = split_book(book_dir, book_slug="t")
    q = result.questions[0]
    assert q.question_type == "sentence_rewriting"
    assert q.original_sentence == "This helicopter cost me 240 yuan."
    assert q.instruction == "改为否定句"
    assert q.template is not None and "________" in q.template
    assert q.answer == "didn't cost"


def test_sentence_rewriting_single_paragraph_inline(tmp_path: Path) -> None:
    """Yimo 4.10/15: original + instruction + template all on one line."""
    book_dir = _write_book(tmp_path, {
        "单项选择.md": "# 1 单项选择\n\n## 1.1 语音\n",
        "词性转换.md": "# 3 词性转换\n\n## 3.1 复数\n",
        "改写句子.md": """
            # 4 改写句子

            ## 4.10 保持句意基本不变

            15.(2020·杨浦·一模)Follow these instructions and you won't make a mistake.(保持句意基本不变)Follow these instructions and you won't________________.
        """,
        "参考答案.md": """
            # 参考答案

            4 改写句子

            4.10 保持句意基本不变

            15.go wrong
        """,
    })
    result = split_book(book_dir, book_slug="t")
    q = result.questions[0]
    assert q.instruction.startswith("保持")
    assert q.template is not None and "________" in q.template
    assert q.answer == "go wrong"


def test_sentence_rewriting_scramble_no_template(tmp_path: Path) -> None:
    """连词成句: no rewrite template. The `original_sentence` is the token bag."""
    book_dir = _write_book(tmp_path, {
        "单项选择.md": "# 1 单项选择\n\n## 1.1 语音\n",
        "词性转换.md": "# 3 词性转换\n\n## 3.1 复数\n",
        "改写句子.md": """
            # 4 改写句子

            ## 4.11 连词成句

            1.（2020·宝山·二模）Tom，to make，tells，every night，stories，his baby sister，go to sleep，her（连词成句）
        """,
        "参考答案.md": """
            # 参考答案

            4 改写句子

            4.11 连词成句

            1.Tom tells his baby sister stories to make her go to sleep every night.
        """,
    })
    result = split_book(book_dir, book_slug="t")
    q = result.questions[0]
    assert q.template is None
    assert q.instruction == "连词成句"
    assert "Tom" in q.answer


# ─────────────────────────────────────────────────────────────────────────────
# answer indexing
# ─────────────────────────────────────────────────────────────────────────────
def test_answer_page_indexing_yimo_style() -> None:
    """一模 answer page has section titles as plain paragraphs (no ##)."""
    md = textwrap.dedent("""
        # 参考答案

        1 单项选择

        1.1 语音

        1.B 2.B 3.B

        1.2 冠词

        1.D 2.A

        3 词性转换

        3.1 名词改复数

        1.proofs 2.months
    """).lstrip()
    idx = parse_answer_page(md)
    assert idx[("single_choice", "1.1 语音", "1")] == "B"
    assert idx[("single_choice", "1.2 冠词", "2")] == "A"
    assert idx[("word_form", "3.1 名词改复数", "2")] == "months"


def test_answer_page_indexing_ermo_style() -> None:
    """二模 answer page has real ## / ### markdown headings."""
    md = textwrap.dedent("""
        # 参考答案

        ## 1 单项选择

        ### 1.1 语音

        1.B 2.D
    """).lstrip()
    idx = parse_answer_page(md)
    assert idx[("single_choice", "1.1 语音", "1")] == "B"
    assert idx[("single_choice", "1.1 语音", "2")] == "D"


# ─────────────────────────────────────────────────────────────────────────────
# JSON writer round-trip
# ─────────────────────────────────────────────────────────────────────────────
def test_write_split_result_roundtrip(tmp_path: Path) -> None:
    """Serialized JSON parses back into RawQuestion."""
    import json as _json

    book_dir = _write_book(tmp_path, {
        "单项选择.md": """
            # 1 单项选择

            ## 1.1 语音

            ( )1.(2020·宝山·一模)Which word rhymes with cat?

            A.hat B.hot C.hit D.hut
        """,
        "词性转换.md": "# 3 词性转换\n\n## 3.1 复数\n",
        "改写句子.md": "# 4 改写句子\n\n## 4.1 否定\n",
        "参考答案.md": "# 参考答案\n\n1 单项选择\n\n1.1 语音\n\n1.A\n",
    })
    result = split_book(book_dir, book_slug="t")

    out_path = tmp_path / "out.json"
    write_split_result(result, out_path)

    loaded = _json.loads(out_path.read_text(encoding="utf-8"))
    assert len(loaded) == 1
    round_tripped = RawQuestion.model_validate(loaded[0])
    assert round_tripped.number == "1"
    assert round_tripped.answer == "A"
