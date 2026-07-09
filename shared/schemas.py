"""Shared data contracts for the entire system.

Pydantic models used by ingestion, AI Engine, and backend.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class KnowledgePoint(BaseModel):
    id: str
    level1: str = Field(..., description="Question type: single_choice / word_form / sentence_rewriting")
    level2: str = Field(..., description="Chinese name of the knowledge point")
    aliases: list[str] = Field(default_factory=list)


class WrongItemRef(BaseModel):
    source_question_id: str
    question_type: str
    knowledge_point_ids: list[str]


class MasteryProfile(BaseModel):
    weak_kps: list[str] = Field(default_factory=list)
    dominant_types: list[str] = Field(default_factory=list)
    total_attempts_considered: int = 0


class GenerateRequest(BaseModel):
    mode: Literal["fresh", "remediation", "review"]
    knowledge_points: list[str] = Field(default_factory=list)
    knowledge_points_exclude: list[str] = Field(default_factory=list)
    question_types: list[Literal["single_choice", "word_form", "sentence_rewriting"]] = Field(default_factory=list)
    difficulty: list[Literal["easy", "medium", "hard"]] = Field(default_factory=list)
    total_questions: int = 10
    type_distribution: dict[str, int] = Field(default_factory=dict)
    difficulty_distribution: dict[str, int] = Field(default_factory=dict)
    per_kp_min: int = 0
    revision_intensity: Literal["fresh", "light", "original"] = "light"
    free_text: str = ""
    wrong_items: list[WrongItemRef] | None = None
    user_id: str | None = None
    review_window_days: int | None = None


class ParserLLMResponse(BaseModel):
    reasoning: str = ""
    knowledge_points: list[str] = Field(default_factory=list)
    knowledge_points_exclude: list[str] = Field(default_factory=list)
    question_types: list[Literal["single_choice", "word_form", "sentence_rewriting"]] = Field(default_factory=list)
    difficulty: list[Literal["easy", "medium", "hard"]] = Field(default_factory=list)
    total_questions: int = 10
    type_distribution: dict[str, int] = Field(default_factory=dict)
    difficulty_distribution: dict[str, int] = Field(default_factory=dict)
    per_kp_min: int = 0
    revision_intensity: Literal["fresh", "light", "original"]


class Question(BaseModel):
    id: str
    book: str
    question_type: Literal["single_choice", "word_form", "sentence_rewriting"]
    chapter_l1: str
    chapter_l2: str
    number: str
    stem: str | None = None
    options: list[dict[str, str]] | None = None
    hint: str | None = None
    original_sentence: str | None = None
    instruction: str | None = None
    template: str | None = None
    answer: str | list[dict] | None = None
    solution: str | None = None
    source_md: str
    source_line: int
    stem_hash: str
    knowledge_point_ids: list[str] = Field(default_factory=list)
    difficulty: Literal["easy", "medium", "hard"] = "medium"


class RevisedQuestion(BaseModel):
    question_type: Literal["single_choice", "word_form", "sentence_rewriting"]
    knowledge_point_ids: list[str] = Field(default_factory=list)
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    stem: str | None = None
    options: list[dict[str, str]] | None = None
    hint: str | None = None
    original_sentence: str | None = None
    instruction: str | None = None
    template: str | None = None
    answer: str | list[dict] | None = None


class PaperItem(BaseModel):
    index: int
    question: RevisedQuestion
    score: int = 2
    source_question_id: str | None = None
    revision_mode: Literal["fresh", "light", "original"] | None = None
    revision_notes: str | None = None


class Paper(BaseModel):
    paper_id: str
    title: str
    generated_at: datetime
    request: GenerateRequest
    items: list[PaperItem]
    total_score: int = 0
    metadata: dict = Field(default_factory=dict)


class RetrievedItem(BaseModel):
    question: Question
    score: float = 0.0
    bucket: str = ""


class RetrievalResult(BaseModel):
    items: list[RetrievedItem]
    warnings: list[str] = Field(default_factory=list)
