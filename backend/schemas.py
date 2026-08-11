from __future__ import annotations

from datetime import datetime
from typing import Literal, TypeAlias

from pydantic import BaseModel, Field

from shared.schemas import Answer, GenerateMode, MasteryProfile, Paper, QuestionType, RevisedQuestion, RevisionMode, WrongItemRef, WritingGradeResult


UserAnswerValue: TypeAlias = str | list[str] | dict[str, str]


class User(BaseModel):
    id: str
    username: str
    created_at: datetime
    role: Literal["user", "admin"] = "user"
    status: Literal["active", "banned"] = "active"


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
    # 用户答错的答案，有值时解析中解释为何错。单选是 "B"，填空/改写是
    # list[str] 或 {blankN: str}，与 GradeSubmissionItem.user_answer 同型。
    user_answer: UserAnswerValue | None = None


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


class WritingGradeItem(BaseModel):
    index: int = Field(ge=1)
    user_essay: str = Field(min_length=1, max_length=2000)


class WritingGradeRequest(BaseModel):
    paper_id: str
    items: list[WritingGradeItem] = Field(min_length=1)


class WritingGradeResultItem(BaseModel):
    index: int
    total_score: float
    content_score: float
    language_score: float
    organization_score: float
    word_count: int
    level: str
    content_analysis: str | None = None
    language_analysis: str | None = None
    organization_analysis: str | None = None
    overall_comment: str | None = None
    revised_version: str | None = None


class WritingGradeResponse(BaseModel):
    paper_id: str
    results: list[WritingGradeResultItem]


class StoredAttemptItem(BaseModel):
    index: int
    source_question_id: str
    knowledge_point_ids: list[str]
    question_type: QuestionType
    is_correct: bool
    user_answer: UserAnswerValue | None = None


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
    # No history field: conversation memory lives server-side (SQLiteSession),
    # keyed by the authenticated user — the client cannot inject/forge turns.
    message: str = Field(min_length=1, max_length=4000)


class AgentChatResponse(BaseModel):
    reply: str
    action: dict | None = None


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    detail: object | None = None
    trace_id: str


# ---- Admin ----


class AdminUserListItem(BaseModel):
    id: str
    username: str
    created_at: datetime
    role: Literal["user", "admin"]
    status: Literal["active", "banned"]
    paper_count: int
    attempt_count: int


class AdminUserList(BaseModel):
    items: list[AdminUserListItem]
    total: int


class AdminUserDetail(BaseModel):
    id: str
    username: str
    created_at: datetime
    role: Literal["user", "admin"]
    status: Literal["active", "banned"]
    paper_count: int
    attempt_count: int
    correct_rate: float | None
    membership_expires_at: str | None


class SetRoleRequest(BaseModel):
    role: Literal["user", "admin"]


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=6, max_length=128)


class AdminOverview(BaseModel):
    total_users: int
    new_users_today: int
    total_papers: int
    total_attempts: int
    active_members: int | None


class TimeseriesPoint(BaseModel):
    day: str
    count: int


class AdminTimeseries(BaseModel):
    users_by_day: list[TimeseriesPoint]
    papers_by_day: list[TimeseriesPoint]


class AdminMembershipItem(BaseModel):
    user_id: str
    username: str | None
    expires_at: str | None
    active: bool


class AdminMembershipListView(BaseModel):
    items: list[AdminMembershipItem]
    total: int


class AdminOrderItem(BaseModel):
    out_trade_no: str
    user_id: str
    username: str | None
    plan_id: str
    amount_cents: int
    status: str
    created_at: str
    paid_at: str | None = None


class AdminOrderListView(BaseModel):
    items: list[AdminOrderItem]


class GrantByUsernameRequest(BaseModel):
    username: str
    days: int = Field(gt=0)


class GrantDaysRequest(BaseModel):
    days: int = Field(gt=0)


class AdminAttemptDay(BaseModel):
    day: str
    attempts: int
    correct_rate: float | None


class AdminTypeAccuracy(BaseModel):
    question_type: str
    total: int
    accuracy: float


class AdminAnalytics(BaseModel):
    site_mastery: MasteryProfile
    attempts_by_day: list[AdminAttemptDay]
    type_accuracy: list[AdminTypeAccuracy]
