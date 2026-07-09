from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field


QuestionType = Literal["single_choice", "word_form", "sentence_rewriting"]
GenerationMode = Literal["fresh", "remediation", "review"]
RevisionMode = Literal["fresh", "light", "original"]
AnswerValue: TypeAlias = str | list[dict[str, list[str]]]
UserAnswerValue: TypeAlias = str | list[str] | dict[str, str]


class Option(BaseModel):
    label: Literal["A", "B", "C", "D"]
    text: str


class QuestionSource(BaseModel):
    book: str
    chapter: str | None = None
    raw_ref: str | None = None


class KnowledgePoint(BaseModel):
    id: str
    level1: str
    level2: str
    parent_id: str | None = None
    aliases: list[str] = Field(default_factory=list)


class Question(BaseModel):
    id: str
    book: str
    question_type: QuestionType
    chapter_l1: str
    chapter_l2: str
    number: str
    stem: str | None = None
    options: list[Option] | None = None
    hint: str | None = None
    original_sentence: str | None = None
    instruction: str | None = None
    template: str | None = None
    answer: AnswerValue
    solution: str | None = None
    knowledge_point_ids: list[str]
    source_md: str
    source_line: int
    stem_hash: str
    created_at: datetime
    version: int = 1


class WrongItemRef(BaseModel):
    knowledge_point_ids: list[str]
    question_type: QuestionType


class GenerateRequest(BaseModel):
    mode: GenerationMode
    knowledge_points: list[str] = Field(default_factory=list)
    knowledge_points_exclude: list[str] = Field(default_factory=list)
    question_types: list[QuestionType] = Field(default_factory=list)
    total_questions: int = 3
    total_score: int | None = None
    type_distribution: dict[str, int] = Field(default_factory=dict)
    revision_intensity: RevisionMode = "light"
    wrong_items: list[WrongItemRef] = Field(default_factory=list)
    user_id: str | None = None
    review_window_days: int | None = None
    free_text: str = ""


class RevisedQuestion(BaseModel):
    stem: str | None = None
    question_type: QuestionType
    options: list[Option] | None = None
    hint: str | None = None
    original_sentence: str | None = None
    instruction: str | None = None
    template: str | None = None
    answer: AnswerValue
    solution: str | None = None
    knowledge_point_ids: list[str]


class PaperItem(BaseModel):
    index: int
    question: RevisedQuestion
    score: int
    source_question_id: str
    revision_mode: RevisionMode
    revision_notes: str | None = None


class Paper(BaseModel):
    paper_id: str
    title: str
    generated_at: datetime
    request: GenerateRequest
    items: list[PaperItem]
    total_score: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class AttemptItem(BaseModel):
    source_question_id: str
    knowledge_point_ids: list[str]
    question_type: QuestionType
    is_correct: bool


class Attempt(BaseModel):
    user_id: str
    paper_id: str
    answered_at: datetime
    items: list[AttemptItem]


class KPMastery(BaseModel):
    knowledge_point_id: str
    attempts: int
    correct_rate: float
    mastery: float


class MasteryProfile(BaseModel):
    user_id: str
    window_days: int | None = None
    weak_kps: list[KPMastery] = Field(default_factory=list)
    dominant_types: list[str] = Field(default_factory=list)
    total_attempts_considered: int = 0


class User(BaseModel):
    id: str
    username: str
    created_at: datetime


class UserRecord(User):
    password_hash: str


class UserCredentials(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(min_length=6, max_length=128)


class Session(BaseModel):
    session_id: str
    user_id: str
    created_at: datetime
    expires_at: datetime


class GeneratePaperRequest(BaseModel):
    user_query: str = Field(min_length=1, max_length=2000)
    mode: GenerationMode = "fresh"
    wrong_items: list[WrongItemRef] | None = None
    review_window_days: int | None = None


class RevisePaperRequest(BaseModel):
    paper_id: str
    user_instruction: str = Field(min_length=1, max_length=2000)


class SolutionRequest(BaseModel):
    question: RevisedQuestion
    source_question_id: str
    revision_mode: RevisionMode


class SolutionResponse(BaseModel):
    solution: str


class GradeSubmissionItem(BaseModel):
    index: int
    user_answer: UserAnswerValue


class GradeSubmissionRequest(BaseModel):
    paper_id: str
    items: list[GradeSubmissionItem]


class GradeResultItem(BaseModel):
    index: int
    user_answer: UserAnswerValue
    correct_answer: AnswerValue
    is_correct: bool


class GradeSubmissionResponse(BaseModel):
    attempt_id: str
    items: list[GradeResultItem]


class PaperListItem(BaseModel):
    paper_id: str
    title: str
    generated_at: datetime
    total_questions: int
    total_score: int
    submitted: bool


class PaperListResponse(BaseModel):
    items: list[PaperListItem]


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    detail: Any | None = None
    trace_id: str


for _model in [
    Option,
    QuestionSource,
    KnowledgePoint,
    Question,
    WrongItemRef,
    GenerateRequest,
    RevisedQuestion,
    PaperItem,
    Paper,
    AttemptItem,
    Attempt,
    KPMastery,
    MasteryProfile,
    User,
    UserRecord,
    Session,
    PaperListItem,
]:
    _model.model_config = ConfigDict(from_attributes=True)
