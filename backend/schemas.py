from __future__ import annotations

from datetime import datetime
from typing import Literal, TypeAlias

from pydantic import BaseModel, Field

from shared.schemas import Answer, GenerateMode, Paper, QuestionType, RevisedQuestion, RevisionMode, WrongItemRef


UserAnswerValue: TypeAlias = str | list[str] | dict[str, str]


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
    mode: GenerateMode = "fresh"
    wrong_items: list[WrongItemRef] | None = None
    review_window_days: int | None = None


class RevisePaperRequest(BaseModel):
    paper_id: str
    user_instruction: str = Field(min_length=1, max_length=2000)


class SolutionRequest(BaseModel):
    question: RevisedQuestion
    source_question_id: str | None = None
    revision_mode: RevisionMode | None = None


class SolutionResponse(BaseModel):
    solution: str


class GradeSubmissionItem(BaseModel):
    index: int = Field(ge=1)
    user_answer: UserAnswerValue


class GradeSubmissionRequest(BaseModel):
    paper_id: str
    items: list[GradeSubmissionItem] = Field(min_length=1)


class GradeResultItem(BaseModel):
    index: int
    user_answer: UserAnswerValue
    correct_answer: Answer
    is_correct: bool


class GradeSubmissionResponse(BaseModel):
    attempt_id: str
    items: list[GradeResultItem]


class StoredAttemptItem(BaseModel):
    index: int
    source_question_id: str
    knowledge_point_ids: list[str]
    question_type: QuestionType
    is_correct: bool


class StoredAttempt(BaseModel):
    user_id: str
    paper_id: str
    answered_at: datetime
    items: list[StoredAttemptItem]


class PaperListItem(BaseModel):
    paper_id: str
    title: str
    generated_at: datetime
    total_questions: int
    submitted: bool


class PaperListResponse(BaseModel):
    items: list[PaperListItem]


class AgentChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    history: list[dict] = Field(default_factory=list)


class AgentChatResponse(BaseModel):
    reply: str
    history: list[dict]
    action: dict | None = None


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    detail: object | None = None
    trace_id: str
