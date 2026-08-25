"""Shared data contracts for all subsystems (Spec A §2 / Spec B §2).

Single source of truth for every pydantic model that crosses a subsystem
boundary. `ingestion` writes these, `ai_engine` reads/produces these, and the
future `backend` serialises them over HTTP. Defined once here so a field change
propagates everywhere.

This file is written to match the **actual** question bank as built (see
`data/questions.db`), not the original spec's idealised design. Notable
reality-driven choices:

  * no `difficulty` field anywhere (dropped — Spec A §1.7)
  * `KnowledgePoint` has no `parent_id` (flat tree — level1 is the parent)
  * `Answer` is a union: single-choice is a bare `str` ("B"); fill-in is a
    list of blank-groups (Spec A §2.2)
  * `Question` mirrors the `questions` table columns 1:1 (options/answer are
    deserialised from the *_json columns)

Model groups (arrow = producer → consumer):
  - Question bank    : Option, KnowledgePoint, Question        ingestion → ai_engine
  - Generation input : WrongItemRef, GenerateRequest           (frontend/)Parser → Retriever
  - Retrieval        : RetrievedItem, RetrievalResult          Retriever → Reviser
                       (RetrievalResult.shortfall carries per-bucket gaps)
  - Paper            : RevisedQuestion, PaperItem, Paper        Reviser → backend → frontend
  - Attempts/mastery : AttemptItem, Attempt                     frontend → backend
                       KPMastery, MasteryProfile                Analyzer → Parser/frontend
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# Shared enums / aliases
# ─────────────────────────────────────────────────────────────────────────────
QuestionType = Literal[
    "single_choice", "word_form", "sentence_rewriting", "listening_single_choice",
    "listening_true_false",
    "listening_fill_blank",
    "reading_longtext_single_choice",
    "cloze_single_choice",
    "reading_first_blank",
    "writing",
]
RevisionMode = Literal["fresh", "light", "original"]
GenerateMode = Literal["fresh", "remediation", "review"]

# The ONLY question types carried in the ChromaDB vector store. These are the
# free-form types worth semantic search; everything else (listening_*, cloze,
# reading_longtext, reading_first_blank) is matched by exact SQL and is
# intentionally SQL-only — it never gets a vector. This is the single source of
# truth for "what belongs in the vector bank", used by the ingestion loader
# (build-vec) and the backend readiness check alike, so they can never drift.
VECTOR_INDEXED_QUESTION_TYPES: frozenset[str] = frozenset(
    {"single_choice", "word_form", "sentence_rewriting"}
)

# Canonical question_type → Chinese display name. Single source of truth for the
# backend (title inference, revise instructions, agent KP catalog) — labels match
# the frontend's TYPE_LABELS (frontend/src/lib/kp.ts) so user-facing wording is
# consistent everywhere. (Previously copy-pasted in reviser/pipeline/coach with a
# 词形/词性 divergence.)
QUESTION_TYPE_LABELS: dict[str, str] = {
    "single_choice": "单项选择",
    "word_form": "词形转换",
    "sentence_rewriting": "句子改写",
    "listening_single_choice": "听力选择",
    "listening_true_false": "听力判断",
    "listening_fill_blank": "听力填词",
    "reading_longtext_single_choice": "阅读理解",
    "cloze_single_choice": "完形填空",
    "reading_first_blank": "阅读首字母填空",
    "writing": "英语作文",
}

# Passage-sharing / no-standard-answer question types. Two independent literals
# used to exist (retriever.PASSAGE_TYPES, reviser._PASSTHROUGH_TYPES) — they must
# stay in lockstep: these types share a passage (revising one breaks the group)
# and writing has no single answer, so the Reviser passes them through unchanged.
PASSAGE_QUESTION_TYPES: frozenset[str] = frozenset(
    {
        "listening_true_false",
        "listening_fill_blank",
        "reading_longtext_single_choice",
        "cloze_single_choice",
        "reading_first_blank",
        "writing",
    }
)


# ─────────────────────────────────────────────────────────────────────────────
# Answer structure (Spec A §2.2)
# ─────────────────────────────────────────────────────────────────────────────
# A fill-in answer is a list of "candidate combinations". Each combination is a
# dict mapping blank name → list of acceptable strings for that blank:
#
#     [{"blank1": ["so"], "blank2": ["that"]}]                     # one combo
#     [{"blank1": ["It's"], "blank2": ["impossible", "hard"]}]      # multi-candidate blank
#     [{"blank1": ["in"], "blank2": ["order"]},                    # two combos
#      {"blank1": ["so"], "blank2": ["as"]}]
#
# A single-choice answer is just a bare label string: "B".
#
# We model a blank-group as a plain dict[str, list[str]] rather than a nested
# model — the blank keys are dynamic ("blank1"/"blank2"/...) and the backend's
# grading logic iterates them positionally, so a typed wrapper adds no value.
BlankGroup = dict[str, list[str]]
Answer = str | list[BlankGroup] | None  # writing questions have null answer


# ─────────────────────────────────────────────────────────────────────────────
# Question bank (Spec A §2.1 / §2.2) — produced by ingestion, read by ai_engine
# ─────────────────────────────────────────────────────────────────────────────
class Option(BaseModel):
    """One choice in a single_choice / listening_true_false question.

    `label` is A-D for single_choice, or T/F for listening_true_false."""
    label: Literal["A", "B", "C", "D", "T", "F"]
    text: str


class KnowledgePoint(BaseModel):
    """A knowledge point. Flat two-level tree: `level1` IS the parent (the
    three fixed question types); `level2` is the concrete 中文 topic name.
    No `parent_id` — the parent is implicit in `level1`."""
    id: str                              # "kp_sc_verbs"
    level1: QuestionType
    level2: str                          # "动词时态与语态"
    aliases: list[str] = Field(default_factory=list)


class Passage(BaseModel):
    """Shared material for long-text questions (listening_true_false /
    reading_longtext_single_choice).

    `content` for listening uses `M:`/`W:` prefixes per line (reuses TTS);
    for reading it is plain prose with `\\n`-separated paragraphs."""
    kind: Literal["listening", "reading"]
    title: str | None = None
    content: str
    audio_url: str | None = None      # reserved: future real audio file path


class Question(BaseModel):
    """A question as stored in the `questions` table (post-ingestion).

    Field-for-field mirror of the SQLite row, except `options` / `answer` are
    the deserialised forms of `options_json` / `answer_json`, and
    `knowledge_point_ids` is joined in from `question_knowledge_points`.

    Content fields are conditionally populated by `question_type`:
      * single_choice     — stem, options
      * word_form         — stem, hint
      * sentence_rewriting — original_sentence, instruction, template
                             (template is None for 连词成句)
    """
    id: str                              # "q_00042"
    book: str                            # "shanghai_2021_yimo"
    question_type: QuestionType
    chapter_l1: str                      # "1 单项选择"
    chapter_l2: str                      # "1.4 不定代词"
    number: str                          # "1" or "1-3"

    # Content (conditional per question_type)
    stem: str | None = None
    options: list[Option] | None = None
    hint: str | None = None
    original_sentence: str | None = None  # may embed <u>...</u> for 对划线部分提问
    instruction: str | None = None
    template: str | None = None

    # Shared material for listening_true_false (null for non-passage types)
    passage_id: str | None = None
    passage_json: Passage | None = None

    # Writing-specific fields (null for non-writing types)
    reference_expressions: str | None = None  # 参考表达，如 "have difficulty in..."
    min_words: int | None = None               # 最低词数要求，如 60

    answer: Answer
    solution: str | None = None          # None until Solutioner fills it on demand
    knowledge_point_ids: list[str] = Field(default_factory=list)

    # Provenance + meta (Spec A §3.8)
    source_md: str
    source_line: int
    created_at: datetime
    version: int = 1


# ─────────────────────────────────────────────────────────────────────────────
# Generation request (Spec B §2.4) — Parser produces, Retriever consumes
# ─────────────────────────────────────────────────────────────────────────────
class WrongItemRef(BaseModel):
    """Frontend hands these to `remediation` mode: metadata of a just-answered
    wrong question. No difficulty field (dropped)."""
    knowledge_point_ids: list[str]
    question_type: QuestionType


class GenerateRequest(BaseModel):
    """Structured generation request. Output of Parser, input of Retriever.

    `difficulty` and its distribution are intentionally absent (Spec A §1.7).
    """
    mode: GenerateMode = "fresh"

    # Filters (empty = unrestricted)
    knowledge_points: list[str] = Field(default_factory=list)
    question_types: list[QuestionType] = Field(default_factory=list)

    total_questions: int

    # Optional distribution constraint: {"single_choice": 5, "word_form": 3}.
    # Keys MUST be QuestionType values (single_choice / word_form /
    # sentence_rewriting) — Parser must not emit typos; Retriever validates.
    # Values should sum to total_questions.
    type_distribution: dict[str, int] = Field(default_factory=dict)

    # Revision intensity — inferred by Parser's LLM, never passed by caller
    revision_intensity: RevisionMode = "light"

    # remediation / review context
    wrong_items: list[WrongItemRef] = Field(default_factory=list)
    user_id: str | None = None
    review_window_days: int | None = None

    # Semantic topic hint — the part of the user's request that the
    # structured fields above CANNOT express (a scenario/theme like "关于环保"
    # / "校园生活" / "购物场景"). Parser fills this ONLY with such leftover
    # topic wording; a pure quota/KP request (e.g. "5 道单选 5 道改写") leaves
    # it "". The Retriever uses it as the query for the semantic (vector) path:
    # non-empty → vector retrieval, empty → SQL random. Do NOT dump the raw
    # user query here — that would make every request trigger vector search.
    free_text: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Retrieval (Spec B §4.1) — Retriever produces, Reviser consumes
# ─────────────────────────────────────────────────────────────────────────────
class RetrievedItem(BaseModel):
    """One candidate question with its retrieval score."""
    question: Question
    score: float                         # semantic similarity (cosine → higher is closer)


class RetrievalResult(BaseModel):
    """Retriever output: candidate pool for the Reviser to pick/transform."""
    items: list[RetrievedItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    # Per-bucket shortfall: how many questions each bucket is short of the
    # requested count, e.g. {"single_choice": 2} means SC needed 5 but only 3
    # were found. Reviser reads this to decide whether to fresh-generate the
    # gap — and whether it's allowed to, per revision_intensity (a user asking
    # for "original" true exam questions should NOT get AI-invented fills;
    # that decision lives in the Reviser, not here). Empty = fully satisfied.
    shortfall: dict[str, int] = Field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# Paper (Spec B) — Reviser produces
# ─────────────────────────────────────────────────────────────────────────────
class RevisedQuestion(BaseModel):
    """A question after revision. Same shape as Question's content fields, but
    without the ingestion meta (id/source/created_at). May equal the original
    verbatim when revision_mode == "original"."""
    question_type: QuestionType
    stem: str | None = None
    options: list[Option] | None = None
    hint: str | None = None
    original_sentence: str | None = None
    instruction: str | None = None
    template: str | None = None
    passage_id: str | None = None
    passage_json: Passage | None = None
    reference_expressions: str | None = None
    min_words: int | None = None
    answer: Answer
    solution: str | None = None
    knowledge_point_ids: list[str] = Field(default_factory=list)


class PaperItem(BaseModel):
    index: int                           # 1-based position in the paper
    question: RevisedQuestion
    source_question_id: str              # traces back to the bank question
    revision_mode: RevisionMode


class Paper(BaseModel):
    paper_id: str                        # uuid hex, minted by ai_engine (Reviser)
    title: str                           # human-readable, inferred by Reviser
    generated_at: datetime
    request: GenerateRequest             # the request that produced it.
                                         # ⚠️ contains user context (user_id /
                                         # wrong_items / review_window_days /
                                         # free_text). The backend persists Paper
                                         # into the `papers` table — mind that
                                         # user_id is already a column there
                                         # (redundant here), and do NOT leak
                                         # wrong_items to the frontend. Revise
                                         # only reads the filter fields.
    items: list[PaperItem]
    metadata: dict[str, Any] = Field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# Attempts & mastery (Spec A §2.5) — backend writes, Analyzer reads
# ─────────────────────────────────────────────────────────────────────────────
class AttemptItem(BaseModel):
    """One graded question inside an attempt. No difficulty field (dropped)."""
    source_question_id: str
    knowledge_point_ids: list[str]
    question_type: QuestionType
    is_correct: bool


class Attempt(BaseModel):
    """Minimal per-paper submission the frontend reports. Stores metadata only —
    not the paper or the question text."""
    user_id: str
    paper_id: str              # AI Engine 生成、后端持久化的 paper_id（Paper.paper_id）
    answered_at: datetime
    items: list[AttemptItem]


class KPMastery(BaseModel):
    knowledge_point_id: str
    attempts: int
    mastery: float                       # Wilson score lower bound (low-sample down-weighted)


class MasteryProfile(BaseModel):
    """Analyzer output, consumed by Parser in review mode."""
    user_id: str
    window_days: int | None
    weak_kps: list[KPMastery]            # ascending mastery, top N
    dominant_types: list[str]            # question types with most wrong answers
    total_attempts_considered: int
    # 写作单独统计：作文不计入对/错正确率（那样会被当 0），改看平均分。
    writing_avg_score: float | None = None   # 已批改作文的平均总分；无则 None
    writing_graded_count: int = 0            # 已批改作文篇数（窗口内）
    writing_full_score: float = 20.0         # 作文满分，用于「X / 20」展示


# ─────────────────────────────────────────────────────────────────────────────
# Writing grading result (Spec J) — Writing Grader produces
# ─────────────────────────────────────────────────────────────────────────────
class WritingGradeResult(BaseModel):
    """单篇作文的批改结果（三维度评分）"""
    total_score: float              # 总分（0-20）
    content_score: float            # 内容得分（0-8）
    language_score: float           # 语言得分（0-8）
    organization_score: float       # 组织结构得分（0-4）
    word_count: int                 # 词数统计
    level: str                      # 档次描述：优秀/良好/合格/待提升
    # 以下字段为会员专属，非会员为 null
    content_analysis: str | None = None      # 内容评析
    language_analysis: str | None = None     # 语言评析（含语法/拼写错误）
    organization_analysis: str | None = None # 组织结构评析
    overall_comment: str | None = None       # 总体评价
    revised_version: str | None = None       # 修改范文
