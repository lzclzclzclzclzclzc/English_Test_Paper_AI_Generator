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
    # 出卷来源页面标签（如 generate / daily / errorbook / drill:single_choice），
    # 存进 paper.metadata["source"] 供管理端「监控看板」统计页面偏好。见 Spec P / 监控看板计划。
    source: str = "unknown"


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
    credits: CreditChargeInfo | None = None


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


class WrongBookHistoryItem(BaseModel):
    source_question_id: str
    question: RevisedQuestion
    revision_mode: RevisionMode
    paper_id: str
    paper_title: str
    graded_at: datetime
    user_answer: UserAnswerValue
    times_wrong: int


class WrongBookHistoryResponse(BaseModel):
    entries: list[WrongBookHistoryItem]


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
    credits: CreditChargeInfo | None = None   # 本次扣费（docs/credits-design.md）


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


class MindmapListItem(BaseModel):
    id: str
    title: str
    knowledge_point: str | None = None
    created_at: str
    updated_at: str


class MindmapListResponse(BaseModel):
    items: list[MindmapListItem]


class MindmapDetail(BaseModel):
    id: str
    title: str
    knowledge_point: str | None = None
    outline_md: str
    created_at: str
    updated_at: str


class MindmapCreateRequest(BaseModel):
    title: str = Field(default="未命名思维导图", max_length=200)
    outline_md: str = Field(default="# 未命名思维导图", max_length=20000)


class MindmapUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    outline_md: str | None = Field(default=None, max_length=20000)


class MindmapCreateResponse(BaseModel):
    id: str


class AgentChatRequest(BaseModel):
    # No history field: conversation memory lives server-side (SQLiteSession),
    # keyed by the authenticated user — the client cannot inject/forge turns.
    message: str = Field(min_length=1, max_length=4000)
    # scope=mindmap: 编辑页内嵌助手，改图上下文。默认 global 不影响现有行为。
    scope: Literal["global", "mindmap"] = "global"
    mindmap_id: str | None = None      # scope=mindmap 时必填
    session_token: str | None = None   # 编辑页临时会话隔离（每次挂载新生成）


class AgentChatResponse(BaseModel):
    reply: str
    action: dict | None = None
    credits: CreditChargeInfo | None = None


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


class VocabularyDailyItem(BaseModel):
    day: str
    studied: int
    new_words: int
    review_words: int


class VocabularyDailyResponse(BaseModel):
    items: list[VocabularyDailyItem]


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
    credits_balance: int = 0
    credits_daily_balance: int = 0


class SetRoleRequest(BaseModel):
    role: Literal["user", "admin"]


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=6, max_length=128)


class AdminOverview(BaseModel):
    total_users: int
    new_users_today: int
    banned_users: int = 0
    total_papers: int
    total_attempts: int
    submitted_papers: int = 0        # 已提交（已作答）试卷数
    paying_users: int = 0           # 至少有一笔 PAID 订单的用户数
    total_revenue_cents: int = 0


class TimeseriesPoint(BaseModel):
    day: str
    count: int


class AdminTimeseries(BaseModel):
    users_by_day: list[TimeseriesPoint]
    papers_by_day: list[TimeseriesPoint]


class AdminCreditAccountItem(BaseModel):
    user_id: str
    username: str | None
    balance: int
    daily_balance: int
    daily_date: str | None = None
    updated_at: str | None = None


class AdminCreditAccountListView(BaseModel):
    items: list[AdminCreditAccountItem]
    total: int


class AdminCreditAccountDetail(BaseModel):
    user_id: str
    username: str | None
    balance: int
    daily_balance: int
    daily_grant: int
    spent_total: int
    ledger: list[CreditLedgerItem]
    ledger_total: int


class AdjustCreditsRequest(BaseModel):
    delta: int = Field(description="正数加、负数减（不会减到 0 以下）")
    note: str = Field(min_length=1, max_length=200)


class AdjustCreditsByUsernameRequest(AdjustCreditsRequest):
    username: str


class AdminOrderItem(BaseModel):
    out_trade_no: str
    user_id: str
    username: str | None
    pack_id: str
    amount_cents: int
    credits: int
    status: str
    channel: str = "qr"
    created_at: str
    paid_at: str | None = None


class AdminOrderListView(BaseModel):
    items: list[AdminOrderItem]
    total: int = 0


class AdminAttemptDay(BaseModel):
    day: str
    attempts: int
    correct_rate: float | None


class AdminTypeAccuracy(BaseModel):
    question_type: str
    total: int
    accuracy: float


class AdminVocabularyDay(BaseModel):
    day: str
    studied: int
    new_words: int
    review_words: int


class AdminAnalytics(BaseModel):
    site_mastery: MasteryProfile
    attempts_by_day: list[AdminAttemptDay]
    type_accuracy: list[AdminTypeAccuracy]


class AdminUserAnalytics(BaseModel):
    """Single-user answering analytics for the admin learner view."""
    attempts_by_day: list[AdminAttemptDay]
    type_accuracy: list[AdminTypeAccuracy]
    vocabulary_by_day: list[AdminVocabularyDay]


# ---- Admin Pro (Spec H) ----


class AdminUserPaperItem(BaseModel):
    id: str
    title: str
    generated_at: datetime
    question_count: int


class AdminUserPaperList(BaseModel):
    items: list[AdminUserPaperItem]


class AdminUserAttemptItem(BaseModel):
    attempt_id: str
    paper_title: str
    answered_at: datetime
    item_total: int
    item_correct: int
    correct_rate: float | None


class AdminUserAttemptList(BaseModel):
    items: list[AdminUserAttemptItem]


class QuestionBankTypeStat(BaseModel):
    question_type: str
    count: int


class QuestionBankKpStat(BaseModel):
    knowledge_point_id: str
    level1: str
    level2: str
    count: int


class QuestionBankChapterStat(BaseModel):
    book: str
    chapter_l1: str
    chapter_l2: str
    count: int


class QuestionBankStats(BaseModel):
    total: int
    by_type: list[QuestionBankTypeStat]
    by_knowledge_point: list[QuestionBankKpStat]
    by_chapter: list[QuestionBankChapterStat]


class QuestionBankListItem(BaseModel):
    id: str
    question_type: str
    book: str
    chapter_l1: str
    chapter_l2: str
    stem: str
    options: list[dict] | None = None
    answer: object | None = None
    knowledge_point_ids: list[str]


class QuestionBankList(BaseModel):
    items: list[QuestionBankListItem]
    total: int


class AdminRevenueDayPoint(BaseModel):
    day: str
    cents: int


class AdminPackRevenue(BaseModel):
    pack_id: str
    orders: int
    cents: int


class AdminRevenue(BaseModel):
    total_cents: int
    revenue_by_day: list[AdminRevenueDayPoint]
    by_pack: list[AdminPackRevenue]


# ---- Usage monitoring (监控看板) ----


class AdminUsageActionPoint(BaseModel):
    """每个付费 AI 动作（credit_ledger.action）的调用量与积分消耗。"""
    action: str
    count: int
    credits_spent: int


class AdminUsageSourcePoint(BaseModel):
    """出卷来源页面（paper.metadata.source）的出卷次数——回答页面偏好。"""
    source: str
    count: int


class AdminUsageModePoint(BaseModel):
    """出卷类型（request.mode：fresh/remediation/review）的分布。"""
    mode: str
    count: int


class AdminUsageWriting(BaseModel):
    count: int
    avg_score: float | None = None


class AdminUsageDayCredits(BaseModel):
    day: str
    credits: int


class AdminUsageSpender(BaseModel):
    user_id: str
    username: str | None = None
    credits_spent: int


class AdminUsage(BaseModel):
    by_action: list[AdminUsageActionPoint]
    by_source: list[AdminUsageSourcePoint]
    by_mode: list[AdminUsageModePoint]
    writing: AdminUsageWriting
    vocabulary_by_day: list[AdminVocabularyDay]
    credits_by_day: list[AdminUsageDayCredits]
    top_spenders: list[AdminUsageSpender]


class AdminAuditItem(BaseModel):
    id: int
    actor_user_id: str
    actor_username: str | None
    action: str
    target_user_id: str | None
    target_username: str | None
    detail: dict | None = None
    created_at: datetime


class AdminAuditList(BaseModel):
    items: list[AdminAuditItem]
    total: int


class AdminSystemHealth(BaseModel):
    llm: bool
    payment_mock: bool
    question_bank_total: int
    app_db_size_kb: int


# ---- credits / payment (docs/credits-design.md) ----

OrderStatus: TypeAlias = Literal["CREATED", "PAID", "EXPIRED", "CLOSED"]
# qr = 当面付扫码(需沙箱版支付宝 App);web = 电脑网站支付(桌面浏览器收银台)
PayChannel: TypeAlias = Literal["qr", "web"]


class CreditAccountView(BaseModel):
    balance: int                 # 付费 / 赠送余额（不过期）
    daily_balance: int           # 今日赠送剩余（当日有效）
    daily_grant: int             # 每日赠送额度（配置）
    total: int                   # balance + daily_balance，即当前可用
    spent_total: int             # 累计消费


class CreditPriceItem(BaseModel):
    action: str
    label: str
    base: int
    per_unit: int
    unit: str
    note: str


class CreditPriceTable(BaseModel):
    items: list[CreditPriceItem]
    signup_bonus: int
    daily_grant: int


class CreditLedgerItem(BaseModel):
    id: int
    delta: int
    bucket: Literal["daily", "balance"]
    balance_after: int
    kind: str
    action: str | None = None
    ref_type: str | None = None
    ref_id: str | None = None
    note: str | None = None
    created_at: str


class CreditLedgerList(BaseModel):
    items: list[CreditLedgerItem]
    total: int


class CreditChargeInfo(BaseModel):
    """付费动作响应里附带的本次扣费信息。"""

    cost: int
    balance_after: int
    daily_after: int


class VocabularyExampleRequest(BaseModel):
    word_id: str = Field(min_length=1, max_length=80)


class VocabularyExampleResponse(BaseModel):
    word_id: str
    example_en: str
    example_zh: str
    credits: CreditChargeInfo


class PackOut(BaseModel):
    id: str
    name: str
    credits: int
    amount_cents: int
    description: str


class PaymentConfigOut(BaseModel):
    mock_pay: bool


class CreateOrderIn(BaseModel):
    pack_id: str
    channel: PayChannel = "qr"


class OrderOut(BaseModel):
    out_trade_no: str
    pack_id: str
    amount_cents: int
    credits: int
    status: OrderStatus
    channel: PayChannel
    qr_code: str | None
    pay_url: str | None
    created_at: str
    expires_at: str
    paid_at: str | None
