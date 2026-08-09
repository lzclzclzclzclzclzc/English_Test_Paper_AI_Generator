from __future__ import annotations

from datetime import datetime
from typing import Literal, TypeAlias

from pydantic import BaseModel, Field

from shared.schemas import Answer, GenerateMode, MasteryProfile, Paper, QuestionType, RevisedQuestion, RevisionMode, WrongItemRef


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


# ---- Vocabulary -------------------------------------------------------------

VocabularyRating = Literal["known", "fuzzy", "forgot"]


class VocabularyCardPrompt(BaseModel):
    word_id: str
    term: str
    origin: Literal["scheduled_review", "new"]
    retry_count: int = 0


class VocabularyCardDetail(BaseModel):
    word_id: str
    term: str
    part_of_speech: str
    meanings: list[str]
    example_en: str
    example_zh: str


class VocabularyTaskCounts(BaseModel):
    scheduled_review_total: int
    scheduled_review_completed: int
    new_total: int
    new_completed: int
    retry_total: int
    retry_completed: int
    retry_pending: int
    remaining_count: int


class VocabularyTodayResponse(BaseModel):
    date: str
    daily_new_limit: int
    phase: Literal["scheduled_review", "new", "same_day_retry", "completed"]
    current_card: VocabularyCardPrompt | None
    counts: VocabularyTaskCounts


class VocabularyJudgmentRequest(BaseModel):
    word_id: str = Field(min_length=1, max_length=80)
    rating: VocabularyRating


class VocabularyJudgmentResponse(BaseModel):
    word_id: str
    rating: VocabularyRating
    detail: VocabularyCardDetail
    next_due_at: datetime
    stage: int
    added_to_same_day_retry: bool
    phase: Literal["scheduled_review", "new", "same_day_retry", "completed"]
    counts: VocabularyTaskCounts


class VocabularyProgressResponse(BaseModel):
    date: str
    daily_new_limit: int
    new_completed: int
    review_completed: int
    same_day_retry_pending: int
    same_day_retry_completed: int
    due_count: int
    learned_count: int
    mastered_count: int
    total_words: int
    streak_days: int
    wordlist_label: str
    source_url: str
    wordlist_sources: list["VocabularyWordlistSource"]


class VocabularyWordlistSource(BaseModel):
    category: Literal["national_core", "shanghai_extension"]
    label: str
    source_url: str


class VocabularySettingsRequest(BaseModel):
    daily_new_limit: int = Field(ge=10, le=50)


class VocabularySettingsResponse(BaseModel):
    daily_new_limit: int
    today_new_cards_added: int


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
