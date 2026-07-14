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
QuestionType = Literal["single_choice", "word_form", "sentence_rewriting"]
RevisionMode = Literal["fresh", "light", "original"]
GenerateMode = Literal["fresh", "remediation", "review"]


# ─────────────────────────────────────────────────────────────────────────────
# Answer structure (Spec A §2.2)
# ─────────────────────────────────────────────────────────────────────────────
BlankGroup = dict[str, list[str]]
Answer = str | list[BlankGroup]


# ─────────────────────────────────────────────────────────────────────────────
# Question bank (Spec A §2.1 / §2.2) — produced by ingestion, read by ai_engine
# ─────────────────────────────────────────────────────────────────────────────
class Option(BaseModel):
    """One choice in a single_choice question."""
    label: Literal["A", "B", "C", "D"]
    text: str


class KnowledgePoint(BaseModel):
    """A knowledge point. Flat two-level tree: `level1` IS the parent (the
    three fixed question types); `level2` is the concrete 中文 topic name.
    No `parent_id` — the parent is implicit in `level1`."""
    id: str                              # "kp_sc_verbs"
    level1: QuestionType
    level2: str                          # "动词时态与语态"
    aliases: list[str] = Field(default_factory=list)


class Question(BaseModel):
    """A question as stored in the `questions` table (post-ingestion)."""
    id: str                              # "q_00042"
    book: str                            # "shanghai_2021_yimo"
    question_type: QuestionType
    chapter_l1: str                      # "1 单项选择"
    chapter_l2: str                      # "1.4 不定代词"
    number: str                          # "1" or "1-3"

    stem: str | None = None
    options: list[Option] | None = None
    hint: str | None = None
    original_sentence: str | None = None  # may embed <u>...</u> for 对划线部分提问
    instruction: str | None = None
    template: str | None = None

    answer: Answer
    solution: str | None = None          # None until Solutioner fills it on demand
    knowledge_point_ids: list[str] = Field(default_factory=list)

    source_md: str
    source_line: int
    stem_hash: str                       # for deduplication
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
    """Structured generation request. Output of Parser, input of Retriever."""
    mode: GenerateMode = "fresh"

    knowledge_points: list[str] = Field(default_factory=list)
    knowledge_points_exclude: list[str] = Field(default_factory=list)
    question_types: list[QuestionType] = Field(default_factory=list)

    total_questions: int = 10

    type_distribution: dict[str, int] = Field(default_factory=dict)
    per_kp_min: int = 0

    revision_intensity: RevisionMode = "light"

    wrong_items: list[WrongItemRef] = Field(default_factory=list)
    user_id: str | None = None
    review_window_days: int | None = None

    free_text: str = ""


class ParserLLMResponse(BaseModel):
    """Parser LLM output format."""
    reasoning: str = ""
    knowledge_points: list[str] = Field(default_factory=list)
    knowledge_points_exclude: list[str] = Field(default_factory=list)
    question_types: list[QuestionType] = Field(default_factory=list)
    total_questions: int = 10
    type_distribution: dict[str, int] = Field(default_factory=dict)
    per_kp_min: int = 0
    revision_intensity: RevisionMode


# ─────────────────────────────────────────────────────────────────────────────
# Retrieval (Spec B §4.1) — Retriever produces, Reviser consumes
# ─────────────────────────────────────────────────────────────────────────────
class RetrievedItem(BaseModel):
    """One candidate question with its retrieval score."""
    question: Question
    score: float                         # semantic similarity (cosine → higher is closer)
    bucket: str = ""                     # question type bucket


class RetrievalResult(BaseModel):
    """Retriever output: candidate pool for the Reviser to pick/transform."""
    items: list[RetrievedItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    shortfall: dict[str, int] = Field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# Paper (Spec B) — Reviser produces
# ─────────────────────────────────────────────────────────────────────────────
class RevisedQuestion(BaseModel):
    """A question after revision. Same shape as Question's content fields, but
    without the ingestion meta (id/source/created_at)."""
    question_type: QuestionType
    stem: str | None = None
    options: list[Option] | None = None
    hint: str | None = None
    original_sentence: str | None = None
    instruction: str | None = None
    template: str | None = None
    answer: Answer
    solution: str | None = None
    knowledge_point_ids: list[str] = Field(default_factory=list)


class PaperItem(BaseModel):
    index: int                           # 1-based position in the paper
    question: RevisedQuestion
    score: int                           # points for this item
    source_question_id: str              # traces back to the bank question
    revision_mode: RevisionMode
    revision_notes: str | None = None    # failure reason if any


class Paper(BaseModel):
    paper_id: str                        # uuid hex, minted by ai_engine (Reviser)
    title: str                           # human-readable, inferred by Reviser
    generated_at: datetime
    request: GenerateRequest
    items: list[PaperItem]
    total_score: int                     # sum of PaperItem.score (set by Reviser)
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
    """Minimal per-paper submission the frontend reports."""
    user_id: str
    paper_id: str
    answered_at: datetime
    items: list[AttemptItem]


class KPMastery(BaseModel):
    knowledge_point_id: str
    attempts: int
    mastery: float                       # Wilson score lower bound


class MasteryProfile(BaseModel):
    """Analyzer output, consumed by Parser in review mode."""
    user_id: str
    window_days: int | None
    weak_kps: list[KPMastery]            # ascending mastery, top N
    dominant_types: list[str]            # question types with most wrong answers
    total_attempts_considered: int