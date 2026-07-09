"""Stage 2 of the ingestion pipeline: Markdown → structured RawQuestion list.

Spec A § 3.3 originally called for a ChapterNode tree with per-leaf `body`. In
practice the four hand-curated markdown files per book (单项选择/词性转换/
改写句子/参考答案) are so regular that we can push the split all the way to
individual questions right here, without an LLM. The downstream extractor
(§ 3.5) is then left with a much narrower job: only `difficulty` and
`knowledge_point_ids` need model inference. This keeps hallucination surface
minimal — everything mechanically decidable is decided mechanically.

Per-question-type contract:

  * single_choice  (# 1 单项选择)
      opener       "( )N." (yimo, half-width) or "（ ）N." (ermo, full-width);
                   variants use "N-K." (e.g. "1-1.") inside 【同考点汇总】.
      stem         line body after `(2020·区名·一模/二模)` prefix.
      options      next non-blank paragraph — either single-line
                   "A.foo B.bar C.baz D.qux" or four separate paragraphs
                   "A.foo" / "B.bar" / ... Questions whose original book
                   embedded options as an image are missing here (see § 1.1:
                   no images). We surface them as `discard_reason="no_options"`
                   and never emit them.

  * word_form      (# 3 词性转换)
      opener       "N." (no prefix parens).
      hint         trailing "(word)" giving the base word.
      no options.

  * sentence_rewriting  (# 4 改写句子)
      opener       "N." — first paragraph ends with "(改为...)"/"(保持...)"/... .
      original     first paragraph, stripped of prefix and instruction.
      template     next paragraph (usually contains "________").
      instruction  the parenthesised directive.
      no options.

Answers come from 参考答案.md, indexed by (question_type, chapter_l2, number).
Questions with no answer match are surfaced via `discard_reason="no_answer"`
and skipped.

The output list is deliberately flat (no ChapterNode tree). Chapter hierarchy
lives in the two string fields `chapter_l1` / `chapter_l2`; that is enough for
every downstream consumer we've identified (knowledge-tree builder, retriever,
extractor).
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Output contract
# ─────────────────────────────────────────────────────────────────────────────
QuestionType = Literal["single_choice", "word_form", "sentence_rewriting"]


class Option(BaseModel):
    label: Literal["A", "B", "C", "D"]
    text: str


class RawQuestion(BaseModel):
    """One question parsed straight out of markdown — pre-LLM.

    The downstream LLM stage only needs to add `difficulty` and
    `knowledge_point_ids`; everything else is filled deterministically here.
    """
    book: str
    question_type: QuestionType
    chapter_l1: str           # e.g. "1 单项选择"
    chapter_l2: str           # e.g. "1.1 语音"  (== KP level2 candidate)
    number: str               # "1" or "3-1" (variant); string, not int
    # `is_variant` (whether this belongs to 【同考点汇总】) is intentionally
    # NOT emitted — a caller can still recover it via `"-" in number`. Kept
    # internally on _Block for the two-phase parse; dropped from the output.

    # Content — populated conditionally per question_type.
    stem: str | None = None                # single_choice / word_form
    options: list[Option] | None = None    # single_choice only
    hint: str | None = None                # word_form only

    original_sentence: str | None = None   # sentence_rewriting
    instruction: str | None = None         # sentence_rewriting
    template: str | None = None            # sentence_rewriting

    answer: str | None = None              # None → discarded upstream; here only for well-formed

    # Traceability.
    source_md: str            # relative to project root
    source_line: int          # 1-based line number of the opener


# ─────────────────────────────────────────────────────────────────────────────
# Shared regex helpers
# ─────────────────────────────────────────────────────────────────────────────
# Numbering: optional leading "( )" / "（ ）" (single_choice only), then digits,
# optional "-K" for 【同考点汇总】 variants, then "." or "．".
_OPENER_RE = re.compile(
    r"""^
        (?:[(（]\s*[)）])?              # optional empty parens (single_choice)
        (?P<num>\d+(?:[-－]\d+)?)      # 1  or  1-1  or  1－1  (full-width dash)
        [．.]                           # half- or full-width period
        \s*
        (?P<rest>.*)$
    """,
    re.VERBOSE,
)

# "(2020·宝山·一模)" or "（2020·宝山·二模）" — attribution, discarded.
_ATTRIBUTION_RE = re.compile(
    r"""^
        [(（]\s*
        (?:20\d{2}\s*[·・])?            # optional year
        [^（）()]{1,20}?                 # region
        \s*[·・]\s*
        [一二三]模
        \s*[)）]
        \s*
    """,
    re.VERBOSE,
)

# Level-1 heading  ("# 1 单项选择")
_L1_RE = re.compile(r"^#\s+(.+?)\s*$")
# Level-2 heading  ("## 1.1 语音")
_L2_RE = re.compile(r"^##\s+(.+?)\s*$")
# 【同考点汇总】 marker — switches subsequent questions to `is_variant=True`.
_VARIANT_MARKER = "【同考点汇总】"


# ─────────────────────────────────────────────────────────────────────────────
# Blocking: cut markdown into per-question chunks, tagged by chapter_l2
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class _Block:
    """A raw question chunk before type-specific parsing."""
    chapter_l1: str
    chapter_l2: str
    number: str
    is_variant: bool
    paragraphs: list[str]  # non-empty, in file order
    source_line: int       # 1-based line of the opener


def _iter_paragraphs(md: str) -> list[tuple[int, str]]:
    """Split markdown into paragraphs, keeping the 1-based line number of the
    first non-blank line of each paragraph."""
    paras: list[tuple[int, str]] = []
    buf: list[str] = []
    buf_start = 0
    for lineno, line in enumerate(md.splitlines(), start=1):
        if line.strip() == "":
            if buf:
                paras.append((buf_start, "\n".join(buf).rstrip()))
                buf = []
                buf_start = 0
        else:
            if not buf:
                buf_start = lineno
            buf.append(line)
    if buf:
        paras.append((buf_start, "\n".join(buf).rstrip()))
    return paras


def _block_markdown(md: str) -> list[_Block]:
    """Cut a body md file (一/二级章节标题 + 题目) into per-question blocks.

    Rules:
      * `# ...` sets chapter_l1
      * `## ...` sets chapter_l2 and resets is_variant to False
      * `【同考点汇总】` line flips is_variant to True for the rest of this
        chapter_l2
      * A paragraph starting with `(...) N.` / `（ ）N.` / `N.` opens a block;
        subsequent paragraphs (until the next opener/heading/marker) belong
        to that block.
    """
    paras = _iter_paragraphs(md)

    blocks: list[_Block] = []
    chapter_l1 = ""
    chapter_l2 = ""
    is_variant = False
    current: _Block | None = None

    def _flush() -> None:
        nonlocal current
        if current is not None and current.paragraphs:
            blocks.append(current)
        current = None

    for start_line, para in paras:
        # Headings live as their own paragraphs.
        m = _L1_RE.match(para)
        if m:
            _flush()
            chapter_l1 = m.group(1)
            is_variant = False
            continue
        m = _L2_RE.match(para)
        if m:
            _flush()
            chapter_l2 = m.group(1)
            is_variant = False
            continue

        # 【同考点汇总】 stands alone (or occasionally with trailing whitespace).
        if para.strip() == _VARIANT_MARKER:
            _flush()
            is_variant = True
            continue

        # Question opener?
        opener = _OPENER_RE.match(para.splitlines()[0])
        if opener and chapter_l2:
            _flush()
            # Normalize the variant separator: books mix half-width `-` and
            # full-width `－`; downstream (RawQuestion.number, answer index)
            # only sees half-width.
            raw_num = opener.group("num").replace("－", "-")
            current = _Block(
                chapter_l1=chapter_l1,
                chapter_l2=chapter_l2,
                number=raw_num,
                is_variant=is_variant or "-" in raw_num,
                paragraphs=[para],
                source_line=start_line,
            )
            continue

        # Continuation of the current block.
        if current is not None:
            current.paragraphs.append(para)

    _flush()
    return blocks


# ─────────────────────────────────────────────────────────────────────────────
# Type-specific parsers
# ─────────────────────────────────────────────────────────────────────────────
_OPTION_INLINE_RE = re.compile(
    r"(?P<label>[A-D])[．.\)、]\s*(?P<text>.*?)(?=\s+[A-D][．.\)、]|$)",
)
_OPTION_STANDALONE_RE = re.compile(r"^\s*(?P<label>[A-D])[．.\)、]\s*(?P<text>.+)$")


def _strip_attribution(text: str) -> str:
    """Drop leading `(2020·宝山·一模)` / `（2020·宝山·二模）` if present."""
    return _ATTRIBUTION_RE.sub("", text, count=1).strip()


def _parse_options(paragraphs: list[str]) -> list[Option] | None:
    """Try to parse A./B./C./D. options from one or more paragraphs.

    Returns None when nothing option-like is found (image-based options
    → discard upstream). Also returns None if only 1 option is found —
    that's almost always corrupted, not a legitimate short question.
    A partial set (2–4) is returned as-is; callers may still discard.
    """
    if not paragraphs:
        return None

    # Multi-paragraph form: each of A./B./C./D. on its own paragraph.
    standalone: list[Option] = []
    for para in paragraphs:
        first_line = para.splitlines()[0]
        m = _OPTION_STANDALONE_RE.match(first_line)
        if not m:
            standalone = []
            break
        # The option text may span multiple lines within one paragraph —
        # join them, but keep the label off the front.
        text_lines = para.splitlines()
        text_lines[0] = m.group("text")
        standalone.append(Option(label=m.group("label"), text="\n".join(text_lines).strip()))
    # A well-formed multi-paragraph option list is 2–4 items all with
    # distinct labels ascending from A.
    if standalone and _looks_like_options(standalone):
        return standalone

    # Single-paragraph form: "A.foo B.bar C.baz D.qux" all on one line.
    joined = " ".join(p.replace("\n", " ") for p in paragraphs)
    inline = [
        Option(label=m.group("label"), text=m.group("text").strip())
        for m in _OPTION_INLINE_RE.finditer(joined)
    ]
    if _looks_like_options(inline):
        return inline

    return None


def _looks_like_options(opts: list[Option]) -> bool:
    """Ascending distinct A..D labels, 2 or more of them."""
    if len(opts) < 2:
        return False
    labels = [o.label for o in opts]
    if labels != sorted(set(labels)):
        return False
    # First label must be A (some texts drop D but never A).
    return labels[0] == "A"


def _parse_single_choice(block: _Block, book: str, source_md: str) -> tuple[RawQuestion | None, str | None]:
    """Return (question, discard_reason).

    discard_reason ∈ {"no_options", None}. Answer wiring is done by caller.
    """
    stem_para = block.paragraphs[0]
    opener = _OPENER_RE.match(stem_para.splitlines()[0])
    assert opener is not None  # blocker guarantees this
    stem_first_line = opener.group("rest")
    # Later lines of the first paragraph are stem continuation, not options
    # (options always sit in a separate paragraph).
    stem_rest = stem_para.splitlines()[1:]
    stem_text = _strip_attribution("\n".join([stem_first_line] + stem_rest)).strip()

    options = _parse_options(block.paragraphs[1:])
    if options is None or len(options) < 2:
        return None, "no_options"

    return (
        RawQuestion(
            book=book,
            question_type="single_choice",
            chapter_l1=block.chapter_l1,
            chapter_l2=block.chapter_l2,
            number=block.number,
            stem=stem_text,
            options=options,
            source_md=source_md,
            source_line=block.source_line,
        ),
        None,
    )


_HINT_TRAILING_RE = re.compile(r"[(（]\s*([A-Za-z][A-Za-z\-\s]*?)\s*[)）]\s*$")
# Fallback: any parenthesised English word anywhere in the block. Used when
# the hint is followed by more Chinese text (e.g. 3.13/1: "…the ______ in the
# world?(loud)—It might be…"). Prefer the LAST such match — hints tend to
# come after the blank, and question stems occasionally include earlier
# English abbreviations in parentheses.
_HINT_ANY_RE = re.compile(r"[(（]\s*([A-Za-z][A-Za-z\-\s]{0,25}?)\s*[)）]")


def _parse_word_form(block: _Block, book: str, source_md: str) -> tuple[RawQuestion | None, str | None]:
    """Word-form questions are usually single-paragraph. Trailing "(word)" is
    the hint. Some questions have the hint mid-line (before a trailing dash)
    or spread across paragraphs; we handle both."""
    # Join all paragraphs so multi-段 stems (rare, seen in 一模 3.4/11) still
    # find the hint.
    para_full = "\n".join(block.paragraphs)
    opener = _OPENER_RE.match(para_full.splitlines()[0])
    assert opener is not None
    first_line = opener.group("rest")
    rest_lines = para_full.splitlines()[1:]
    body = _strip_attribution("\n".join([first_line] + rest_lines)).strip()

    hint_match = _HINT_TRAILING_RE.search(body)
    if not hint_match:
        # Fallback: last parenthesised English token anywhere in body.
        candidates = list(_HINT_ANY_RE.finditer(body))
        if candidates:
            hint_match = candidates[-1]
        else:
            return None, "no_hint"
    hint = hint_match.group(1).strip()
    stem_text = (body[: hint_match.start()] + body[hint_match.end():]).rstrip().rstrip("(（").rstrip()

    if "________" not in stem_text and "___" not in stem_text:
        # Blank collapsed away → very likely an image-based question. Discard.
        return None, "no_blank"

    return (
        RawQuestion(
            book=book,
            question_type="word_form",
            chapter_l1=block.chapter_l1,
            chapter_l2=block.chapter_l2,
            number=block.number,
            stem=stem_text,
            hint=hint,
            source_md=source_md,
            source_line=block.source_line,
        ),
        None,
    )


_INSTRUCTION_TRAILING_RE = re.compile(
    r"[(（]\s*("
    r"改[为成][^)）]+|"
    r"保持[^)）]*|"                    # "保持句意基本不变" / "保持原句意思" / ...
    r"连词成句[^)）]*|"
    r"合并[^)）]+|"
    r"对[^)）]*划线[^)）]*提问[^)）]*"
    r")\s*[)）]\s*"
)
# Some 2021 二模 questions have a typo missing the leading '（' (e.g.
# `对划线部分提问）` at ermo 改写句子.md:119). Accept a naked ")" instruction
# too, but only when it matches a canonical directive.
_INSTRUCTION_LOOSE_RE = re.compile(
    r"("
    r"改[为成][^)）\s]{1,10}|"
    r"保持句意[^)）\s]{0,10}|"
    r"保持原句意[^)）\s]{0,10}|"
    r"连词成句|"
    r"合并[^)）\s]{1,10}|"
    r"对划线部分提问"
    r")[)）]\s*"
)


def _parse_sentence_rewriting(block: _Block, book: str, source_md: str) -> tuple[RawQuestion | None, str | None]:
    """Sentence-rewriting layouts we accept:

      (a) Two paragraphs — original+`(改为…)` then a template with `________`.
      (b) Single paragraph, everything on one line (一模 4.10/15).
      (c) 连词成句 — the instruction stays the same as chapter_l2, but there
          is NO template paragraph. Answer is the reordered sentence.
    """
    first_para = block.paragraphs[0]
    opener = _OPENER_RE.match(first_para.splitlines()[0])
    assert opener is not None
    first_line = opener.group("rest")
    rest_lines = first_para.splitlines()[1:]
    first_body = _strip_attribution("\n".join([first_line] + rest_lines)).strip()

    # 连词成句 is a whole sub-genre where the "question" is a bag of tokens
    # and no rewrite template exists. Detect by chapter or by trailing
    # `(连词成句)` marker.
    is_scramble = ("连词成句" in block.chapter_l2) or ("连词成句" in first_body)

    m = _INSTRUCTION_TRAILING_RE.search(first_body)
    if m is None:
        m = _INSTRUCTION_LOOSE_RE.search(first_body)
    if m is None:
        # For 连词成句 the instruction may be omitted entirely — treat the
        # chapter title as the instruction.
        if is_scramble:
            instruction = "连词成句"
            original = first_body
            template = None
        else:
            return None, "no_instruction"
    else:
        instruction = m.group(1).strip()
        # Whatever comes AFTER the instruction is the inline template
        # (layout b). BEFORE it is the original sentence.
        original = first_body[: m.start()].rstrip().rstrip("(（").rstrip()
        inline_template = first_body[m.end():].strip()
        template = inline_template if ("________" in inline_template or "___" in inline_template) else None

    # Look for a separate template paragraph if we didn't find an inline one.
    if template is None and len(block.paragraphs) >= 2 and not is_scramble:
        candidate = block.paragraphs[1].strip()
        if "________" in candidate or "___" in candidate:
            template = candidate

    if template is None and not is_scramble:
        return None, "no_template"

    return (
        RawQuestion(
            book=book,
            question_type="sentence_rewriting",
            chapter_l1=block.chapter_l1,
            chapter_l2=block.chapter_l2,
            number=block.number,
            original_sentence=original,
            instruction=instruction,
            template=template,
            source_md=source_md,
            source_line=block.source_line,
        ),
        None,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Answer-page parsing
# ─────────────────────────────────────────────────────────────────────────────
# One answer entry in the answer page. Layout examples:
#   single_choice:  "1.B  2.D  3.B ..."          — many per paragraph
#   word_form:      "1.proofs 2.months 3.factories ..."
#   sentence_rew.:  "1.didn't cost 2.haven't，yet 3.doesn't watch"
# Full-width period after the number is also possible.
_ANSWER_ENTRY_RE = re.compile(
    r"""
        (?P<num>\d+(?:[-－]\d+)?)[．.]
        (?P<ans>.*?)
        (?=(?:\s+\d+(?:[-－]\d+)?[．.])|$)
    """,
    re.VERBOSE,
)

# In the answer page, section headings (like the body files' `##`) are often
# rendered as plain paragraphs — because 一模's EPUB didn't tag those lines
# with any heading class. Detect them by their "N.M title" digit prefix.
_ANSWER_L1_RE = re.compile(r"^(?:#{1,2}\s+)?(?P<txt>\d+\s+\S.*)$")  # "1 单项选择"
_ANSWER_L2_RE = re.compile(r"^(?:#{1,3}\s+)?(?P<txt>\d+\.\d+\s+\S.*)$")  # "1.1 语音"


AnswerKey = tuple[QuestionType, str, str]  # (qtype, chapter_l2, number)


def _l1_to_qtype(l1: str) -> QuestionType | None:
    """"1 单项选择" → single_choice; unknown → None (skip)."""
    if "单项选择" in l1:
        return "single_choice"
    if "词性转换" in l1:
        return "word_form"
    if "改写句子" in l1:
        return "sentence_rewriting"
    return None


def parse_answer_page(md: str) -> dict[AnswerKey, str]:
    """Index answers by (question_type, chapter_l2, number).

    Format-tolerant: works whether section headings arrived as real `##`
    (二模) or as plain paragraphs (一模)."""
    out: dict[AnswerKey, str] = {}
    qtype: QuestionType | None = None
    l2 = ""
    is_variant = False

    paras = _iter_paragraphs(md)
    for _, para in paras:
        first_line = para.splitlines()[0].strip()

        # Level-2 must be tried BEFORE level-1 — "1.1 语音" also matches _ANSWER_L1_RE.
        m2 = _ANSWER_L2_RE.match(first_line)
        if m2:
            l2 = m2.group("txt")
            is_variant = False
            continue
        m1 = _ANSWER_L1_RE.match(first_line)
        if m1 and " " in m1.group("txt"):
            candidate_qtype = _l1_to_qtype(m1.group("txt"))
            if candidate_qtype is not None:
                qtype = candidate_qtype
                l2 = ""              # reset — a new L1 always precedes a new L2
                is_variant = False
                continue
            # Non-target L1 (e.g. "2 选词", "5 阅读理解") — mute answer capture
            # until we enter a target L1 again. Otherwise stray answer lines
            # (e.g. "14.(1)C (2)B ...") would be attributed to the previous
            # qtype+l2 pair and overwrite legitimate answers.
            qtype = None
            l2 = ""
            is_variant = False
            continue
        if first_line == _VARIANT_MARKER:
            is_variant = True
            continue

        if qtype is None or not l2:
            continue

        # Otherwise, treat as an answer-entry paragraph. Full paragraph text
        # (single- or multi-line) is fed to the entry regex.
        text = para.strip()
        for m in _ANSWER_ENTRY_RE.finditer(text):
            # Normalize full-width dash → half-width in the key, matching the
            # body-side normalization in _block_markdown.
            num = m.group("num").replace("－", "-")
            key = (qtype, l2, num)
            answer_text = m.group("ans").strip()
            # Only accept if this looks like it lives inside the current
            # variant context (main list vs 【同考点汇总】). Both are keyed
            # by `number` which itself carries "-K" for variants, so the
            # dict key stays unique either way.
            out[key] = answer_text

    return out


# ─────────────────────────────────────────────────────────────────────────────
# Top-level orchestration
# ─────────────────────────────────────────────────────────────────────────────
BODY_FILES: dict[QuestionType, str] = {
    "single_choice": "单项选择.md",
    "word_form": "词性转换.md",
    "sentence_rewriting": "改写句子.md",
}
ANSWER_FILE = "参考答案.md"


@dataclass
class SplitStats:
    per_type_ok: dict[QuestionType, int] = field(default_factory=lambda: {
        "single_choice": 0, "word_form": 0, "sentence_rewriting": 0,
    })
    discarded: dict[str, int] = field(default_factory=dict)

    def record_ok(self, qtype: QuestionType) -> None:
        self.per_type_ok[qtype] += 1

    def record_discard(self, reason: str) -> None:
        self.discarded[reason] = self.discarded.get(reason, 0) + 1


@dataclass
class SplitResult:
    questions: list[RawQuestion]
    stats: SplitStats


_TYPE_PARSERS = {
    "single_choice": _parse_single_choice,
    "word_form": _parse_word_form,
    "sentence_rewriting": _parse_sentence_rewriting,
}


def split_book(book_md_dir: Path, book_slug: str) -> SplitResult:
    """Parse one book's four markdown files into a flat RawQuestion list.

    Parameters
    ----------
    book_md_dir : Path
        e.g. `data/raw_md/shanghai_2021_yimo/`. Expected to contain the four
        files listed in BODY_FILES + ANSWER_FILE.
    book_slug : str
        Passed through into `RawQuestion.book`; not derived from the path so
        callers can override.
    """
    answer_md = (book_md_dir / ANSWER_FILE).read_text(encoding="utf-8")
    answers = parse_answer_page(answer_md)

    stats = SplitStats()
    questions: list[RawQuestion] = []

    for qtype, filename in BODY_FILES.items():
        md_path = book_md_dir / filename
        if not md_path.is_file():
            log.warning("skipping missing body file: %s", md_path)
            continue
        md_text = md_path.read_text(encoding="utf-8")
        source_md = str(md_path.as_posix())

        for block in _block_markdown(md_text):
            parser = _TYPE_PARSERS[qtype]
            q, discard_reason = parser(block, book_slug, source_md)
            if discard_reason is not None:
                stats.record_discard(f"{qtype}:{discard_reason}")
                log.info(
                    "discard %s %s/%s (%s) at %s:%d",
                    qtype, block.chapter_l2, block.number, discard_reason,
                    md_path.name, block.source_line,
                )
                continue
            assert q is not None

            # Wire the answer.
            answer = answers.get((qtype, q.chapter_l2, q.number))
            if answer is None:
                stats.record_discard(f"{qtype}:no_answer")
                log.info(
                    "no answer for %s %s/%s at %s:%d",
                    qtype, q.chapter_l2, q.number, md_path.name, q.source_line,
                )
                continue
            q.answer = answer

            questions.append(q)
            stats.record_ok(qtype)

    return SplitResult(questions=questions, stats=stats)


def write_split_result(result: SplitResult, out_path: Path) -> None:
    """Serialize `result.questions` to `out_path` (JSON, pretty, utf-8)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [q.model_dump(mode="json") for q in result.questions]
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
