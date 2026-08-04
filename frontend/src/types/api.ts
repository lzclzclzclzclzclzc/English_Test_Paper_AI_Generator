/**
 * 与后端契约对齐的手写 TS 类型。
 *
 * 权威来源：origin/CJN/backend-mvp 分支
 *   - shared/schemas.py（pydantic 模型，字段逐一对应）
 *   - docs/backend-api.md（HTTP 语义）
 *
 * 契约变更时人工同步本文件（Spec D § 4.3，不用 OpenAPI 生成）。
 * datetime 字段一律序列化为 ISO-8601 字符串。
 */

// ---- 字面量联合（schemas.py 顶部 Literal） ----

export type QuestionType = 'single_choice' | 'word_form' | 'sentence_rewriting' | 'listening_single_choice'
export type GenerationMode = 'fresh' | 'remediation' | 'review'
export type RevisionMode = 'fresh' | 'light' | 'original'

/**
 * 正确答案（服务端下发）：
 * - single_choice：单字母字符串，如 "B"
 * - word_form / sentence_rewriting：候选组合列表。
 *   外层数组 = 多种可接受填法（OR）；每个对象的 blankN -> 同义候选数组（OR）。
 *   例：[{ blank1: ["didn't"], blank2: ["cost"] }]
 */
export type AnswerValue = string | Array<Record<string, string[]>>

/**
 * 用户提交的答案：
 * - 单选/单空：字符串
 * - 多空：按空位顺序的数组，或（推荐）blankN 字典
 */
export type UserAnswerValue = string | string[] | Record<string, string>

// ---- 基础构件 ----

export interface Option {
  label: 'A' | 'B' | 'C' | 'D'
  text: string
}

// ---- 题目（试卷内渲染的形态） ----

/** 试卷条目里的题目——前端渲染的唯一题目形态（schemas.py RevisedQuestion）。 */
export interface RevisedQuestion {
  stem: string | null
  question_type: QuestionType
  /** single_choice 有值（A-D 四项）；其余题型为 null */
  options: Option[] | null
  /** word_form：待变形的提示词，如 "proof" */
  hint: string | null
  /** sentence_rewriting：原句 */
  original_sentence: string | null
  /** sentence_rewriting：中文改写指令，如 "改为否定句" */
  instruction: string | null
  /** sentence_rewriting：带空模板。注意下划线连串数 ≠ 空数，空数以 answer[0] 键数为准 */
  template: string | null
  answer: AnswerValue
  solution: string | null
  knowledge_point_ids: string[]
}

// ---- 试卷 ----

export interface WrongItemRef {
  knowledge_point_ids: string[]
  question_type: QuestionType
}

/** Paper.request 内嵌的引擎请求回显（GenerateRequest），前端只读不构造。 */
export interface GenerateRequest {
  mode: GenerationMode
  knowledge_points: string[]
  question_types: QuestionType[]
  total_questions: number
  type_distribution: Record<string, number>
  revision_intensity: RevisionMode
  wrong_items: WrongItemRef[]
  user_id: string | null
  review_window_days: number | null
  free_text: string
}

export interface PaperItem {
  /** 1-based，提交答题时按此回传 */
  index: number
  question: RevisedQuestion
  source_question_id: string
  revision_mode: RevisionMode
}

export interface Paper {
  paper_id: string
  title: string
  generated_at: string
  request: GenerateRequest
  items: PaperItem[]
  metadata: Record<string, unknown>
}

// ---- HTTP 请求体 ----

/** POST /api/papers/generate */
export interface GeneratePaperRequest {
  /** 1-2000 字符 */
  user_query: string
  mode?: GenerationMode
  wrong_items?: WrongItemRef[] | null
  review_window_days?: number | null
}

/** POST /api/papers/revise（返回全新 paper_id 的 Paper） */
export interface RevisePaperRequest {
  paper_id: string
  /** 1-2000 字符 */
  user_instruction: string
}

/** POST /api/solutions */
export interface SolutionRequest {
  question: RevisedQuestion
  source_question_id: string
  revision_mode: RevisionMode
  /** 用户答错的答案，传入后解析会解释为何错（单选是字母，填空/改写是数组或字典） */
  user_answer?: UserAnswerValue | null
}

export interface SolutionResponse {
  solution: string
}

// ---- 判分 ----

export interface GradeSubmissionItem {
  /** >= 1；必须覆盖试卷全部 index 恰好一次，否则 422 request.invalid */
  index: number
  user_answer: UserAnswerValue
}

/** POST /api/attempts */
export interface GradeSubmissionRequest {
  paper_id: string
  /** 至少一项 */
  items: GradeSubmissionItem[]
}

export interface GradeResultItem {
  index: number
  user_answer: UserAnswerValue
  correct_answer: AnswerValue
  is_correct: boolean
}

export interface GradeSubmissionResponse {
  attempt_id: string
  items: GradeResultItem[]
}

// ---- 试卷列表 ----

export interface PaperListItem {
  paper_id: string
  title: string
  generated_at: string
  total_questions: number
  submitted: boolean
}

/** GET /api/papers?limit=&offset= */
export interface PaperListResponse {
  items: PaperListItem[]
}

// ---- 掌握度 ----

export interface KPMastery {
  knowledge_point_id: string
  attempts: number
  /** Wilson lower bound，越低越薄弱 */
  mastery: number
}

/** GET /api/knowledge-points 目录项（用于 id→中文名展示） */
export interface KnowledgePoint {
  id: string
  level1: QuestionType
  level2: string
  aliases: string[]
}

/** GET /api/users/me/mastery?window_days= */
export interface MasteryProfile {
  user_id: string
  window_days: number | null
  weak_kps: KPMastery[]
  dominant_types: string[]
  total_attempts_considered: number
}

// ---- 鉴权 ----

/** register / login / me 的响应 */
export interface User {
  id: string
  username: string
  created_at: string
  role: 'user' | 'admin'
  status: 'active' | 'banned'
}

/** register + login 的请求体。username 3-32 位 [a-zA-Z0-9_]；password 6-128 位 */
export interface UserCredentials {
  username: string
  password: string
}

// ---- Agent 对话 ----
// 对话历史由后端 SQLiteSession 按用户维护，前端只发新消息、不回传 history。

export interface AgentChatRequest {
  message: string
}

export type AgentAction =
  | { type: 'open_paper'; paper_id: string }

export interface AgentChatResponse {
  reply: string
  action: AgentAction | null
}

// ---- 学习计划 ----

export interface StudyPlanDay {
  index: number
  date: string | null       // YYYY-MM-DD
  theme: string
  knowledge_points: string[]
  kp_names: string[]
  question_types: QuestionType[]
  total_questions: number
  note: string
  paper_id: string
  paper_title: string
}

export interface StudyPlan {
  plan_id: string
  user_id: string
  total_days: number
  created_at: string
  days: StudyPlanDay[]
}

// ---- 背单词 ----

export type VocabularyRating = 'known' | 'fuzzy' | 'forgot'

export interface VocabularyCard {
  word_id: string
  term: string
  part_of_speech: string
  meanings: string[]
  example_en: string
  example_zh: string
  card_type: 'review' | 'new'
}

export interface VocabularyToday {
  date: string
  daily_new_limit: number
  new_count: number
  review_count: number
  completed_count: number
  remaining_count: number
  cards: VocabularyCard[]
}

export interface VocabularyReviewResponse {
  word_id: string
  correct_answer: string
  spelling_correct: boolean
  applied_rating: VocabularyRating
  next_due_at: string
  remaining_count: number
}

export interface VocabularyProgress {
  date: string
  daily_new_limit: number
  new_completed: number
  review_completed: number
  due_count: number
  mastered_count: number
  total_words: number
  streak_days: number
  wordlist_label: string
  source_url: string
}


/**
 * 所有业务错误的统一响应体。error_code 稳定清单（backend/errors.py）：
 *   server.internal(500) auth.unauthorized(401) auth.username_conflict(409)
 *   auth.invalid_credentials(401) resource.not_found(404) request.invalid(422)
 *   rate.exceeded(429) ai.parser_failed(400) ai.no_candidate(422)
 *   ai.reviser_failed(500) ai.solutioner_failed(500) ai.llm_upstream(502) ai.internal(500)
 */
export interface ErrorResponse {
  error_code: string
  message: string
  detail: unknown
  trace_id: string
}

// ---- 管理后台 ----
export interface AdminUserListItem {
  id: string
  username: string
  created_at: string
  role: 'user' | 'admin'
  status: 'active' | 'banned'
  paper_count: number
  attempt_count: number
}
export interface AdminUserList { items: AdminUserListItem[]; total: number }
export interface AdminUserDetail extends AdminUserListItem {
  correct_rate: number | null
  membership_expires_at: string | null
}
export interface AdminOverview {
  total_users: number
  new_users_today: number
  total_papers: number
  total_attempts: number
  active_members: number | null
}
export interface TimeseriesPoint { day: string; count: number }
export interface AdminTimeseries { users_by_day: TimeseriesPoint[]; papers_by_day: TimeseriesPoint[] }
export interface AdminMembership { user_id: string; username: string | null; expires_at: string | null; active: boolean }
export interface AdminMembershipList { items: AdminMembership[]; total: number }
export interface AdminOrder {
  out_trade_no: string
  user_id: string
  username: string | null
  plan_id: string
  amount_cents: number
  status: string
  created_at: string
  paid_at: string | null
}
export interface AdminOrderList { items: AdminOrder[] }

export interface AdminAttemptDay { day: string; attempts: number; correct_rate: number | null }
export interface AdminTypeAccuracy { question_type: string; total: number; accuracy: number }
export interface AdminAnalytics {
  site_mastery: MasteryProfile
  attempts_by_day: AdminAttemptDay[]
  type_accuracy: AdminTypeAccuracy[]
}
