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

import type { CreditChargeInfo } from '@/types/payment'

// ---- 字面量联合（schemas.py 顶部 Literal） ----

export type QuestionType = 'single_choice' | 'word_form' | 'sentence_rewriting' | 'listening_single_choice' | 'listening_true_false' | 'listening_fill_blank' | 'reading_longtext_single_choice' | 'cloze_single_choice' | 'reading_first_blank' | 'writing'
export type GenerationMode = 'fresh' | 'remediation' | 'review'
export type RevisionMode = 'fresh' | 'light' | 'original'

/**
 * 正确答案（服务端下发）：
 * - single_choice：单字母字符串，如 "B"
 * - word_form / sentence_rewriting：候选组合列表。
 *   外层数组 = 多种可接受填法（OR）；每个对象的 blankN -> 同义候选数组（OR）。
 *   例：[{ blank1: ["didn't"], blank2: ["cost"] }]
 * - writing：null（作文题无标准答案）
 */
export type AnswerValue = string | Array<Record<string, string[]>> | null

/**
 * 用户提交的答案：
 * - 单选/单空：字符串
 * - 多空：按空位顺序的数组，或（推荐）blankN 字典
 */
export type UserAnswerValue = string | string[] | Record<string, string>

// ---- 基础构件 ----

export interface Option {
  label: 'A' | 'B' | 'C' | 'D' | 'T' | 'F'
  text: string
}

/** 共享材料（listening_true_false 用），对应 schemas.py Passage */
export interface Passage {
  kind: 'listening' | 'reading'
  title: string | null
  content: string
  audio_url: string | null
}

// ---- 题目（试卷内渲染的形态） ----

/** 试卷条目里的题目——前端渲染的唯一题目形态（schemas.py RevisedQuestion）。 */
export interface RevisedQuestion {
  stem: string | null
  question_type: QuestionType
  /** single_choice 有值（A-D 四项）；其余题型为 null */
  options: Option[] | null
  /** word_form：待变形的提示词，如 "proof"；writing：写作提示 */
  hint: string | null
  /** sentence_rewriting：原句 */
  original_sentence: string | null
  /** sentence_rewriting：中文改写指令，如 "改为否定句"；writing：英文指令 */
  instruction: string | null
  /** sentence_rewriting：带空模板。注意下划线连串数 ≠ 空数，空数以 answer[0] 键数为准 */
  template: string | null
  /** listening_true_false：共享材料组 id（同组小题相同） */
  passage_id?: string | null
  /** listening_true_false：共享材料对象（同组小题冗余存储） */
  passage_json?: Passage | null
  /** writing：参考表达，如 "have difficulty in..." */
  reference_expressions?: string | null
  /** writing：最低词数要求，如 60 */
  min_words?: number | null
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
  writing_avg_score: number | null
  writing_graded_count: number
  writing_full_score: number
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
  scope?: 'global' | 'mindmap'
  mindmap_id?: string
  session_token?: string
}

export type AgentAction =
  | { type: 'open_paper'; paper_id: string }
  | { type: 'open_mindmap'; mindmap_id: string }
  | { type: 'mindmap_updated'; mindmap_id: string }

export interface AgentChatResponse {
  reply: string
  action: AgentAction | null
}

// ---- 思维导图 ----

export interface MindmapListItem {
  id: string
  title: string
  knowledge_point?: string | null
  created_at: string
  updated_at: string
}

export interface MindmapListResponse {
  items: MindmapListItem[]
}

export interface MindmapDetail {
  id: string
  title: string
  knowledge_point?: string | null
  outline_md: string
  created_at: string
  updated_at: string
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

export interface VocabularyCardPrompt {
  word_id: string
  term: string
  origin: 'scheduled_review' | 'new'
  retry_count: number
}

export interface VocabularyCardDetail {
  word_id: string
  term: string
  part_of_speech: string
  meanings: string[]
  example_en: string
  example_zh: string
}

export interface VocabularyTaskCounts {
  scheduled_review_total: number
  scheduled_review_completed: number
  new_total: number
  new_completed: number
  retry_total: number
  retry_completed: number
  retry_pending: number
  remaining_count: number
}

export interface VocabularyToday {
  date: string
  daily_new_limit: number
  phase: 'scheduled_review' | 'new' | 'same_day_retry' | 'completed'
  current_card: VocabularyCardPrompt | null
  counts: VocabularyTaskCounts
}

export interface VocabularyJudgmentResponse {
  word_id: string
  rating: VocabularyRating
  detail: VocabularyCardDetail
  next_due_at: string
  stage: number
  added_to_same_day_retry: boolean
  phase: VocabularyToday['phase']
  counts: VocabularyTaskCounts
}

export interface VocabularyExampleResponse {
  word_id: string
  example_en: string
  example_zh: string
  credits: CreditChargeInfo
}

export interface VocabularyProgress {
  date: string
  daily_new_limit: number
  new_completed: number
  review_completed: number
  same_day_retry_pending: number
  same_day_retry_completed: number
  due_count: number
  learned_count: number
  mastered_count: number
  total_words: number
  streak_days: number
  wordlist_label: string
  source_url: string
  wordlist_sources: VocabularyWordlistSource[]
}

export interface VocabularyWordlistSource {
  category: 'national_core' | 'shanghai_extension'
  label: string
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

// ---- 作文批改（Spec J） ----

/** POST /api/writing/grade 的请求体 */
export interface WritingGradeRequest {
  paper_id: string
  items: WritingGradeItem[]
}

export interface WritingGradeItem {
  index: number
  user_essay: string
}

/** POST /api/writing/grade 的响应体 */
export interface WritingGradeResponse {
  paper_id: string
  results: WritingGradeResultItem[]
}

/** 单篇作文的批改结果（三维度评分）。
 *  POST /writing/grade 响应不返回 user_essay；
 *  GET /writing/by-paper 历史回显接口会额外返回 user_essay。 */
export interface WritingGradeResultItem {
  index: number
  total_score: number        // 总分（0-20）
  content_score: number      // 内容得分（0-8）
  language_score: number     // 语言得分（0-8）
  organization_score: number // 组织结构得分（0-4）
  word_count: number         // 词数统计
  level: string              // 档次：优秀/良好/合格/待提升
  user_essay?: string        // 仅历史回显接口携带：用户提交的作文原文
  // 三维详细评析（2026-08 积分制起对所有人返回；历史记录可能为 null）
  content_analysis: string | null      // 内容评析
  language_analysis: string | null     // 语言评析（含语法/拼写错误）
  organization_analysis: string | null // 组织结构评析
  overall_comment: string | null       // 总体评价
  revised_version: string | null       // 修改范文
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
  credits_balance: number
  credits_daily_balance: number
}
export interface AdminOverview {
  total_users: number
  new_users_today: number
  banned_users: number
  total_papers: number
  total_attempts: number
  /** 至少有一笔 PAID 订单的用户数 */
  paying_users: number
  total_revenue_cents: number
}
export interface TimeseriesPoint { day: string; count: number }
export interface AdminTimeseries { users_by_day: TimeseriesPoint[]; papers_by_day: TimeseriesPoint[] }
export interface AdminCreditAccount {
  user_id: string
  username: string | null
  balance: number
  daily_balance: number
  daily_date: string | null
  updated_at: string | null
}
export interface AdminCreditAccountList { items: AdminCreditAccount[]; total: number }
export interface AdminCreditAccountDetail {
  user_id: string
  username: string | null
  balance: number
  daily_balance: number
  daily_grant: number
  spent_total: number
  ledger: import('@/types/payment').CreditLedgerItem[]
  ledger_total: number
}
export interface AdminOrder {
  out_trade_no: string
  user_id: string
  username: string | null
  pack_id: string
  amount_cents: number
  credits: number
  status: string
  channel: string
  created_at: string
  paid_at: string | null
}
export interface AdminOrderList { items: AdminOrder[]; total: number }

export interface AdminAttemptDay { day: string; attempts: number; correct_rate: number | null }
export interface AdminTypeAccuracy { question_type: string; total: number; accuracy: number }
export interface AdminVocabularyDay { day: string; studied: number; new_words: number; review_words: number }
export interface AdminAnalytics {
  site_mastery: MasteryProfile
  attempts_by_day: AdminAttemptDay[]
  type_accuracy: AdminTypeAccuracy[]
}
export interface AdminUserAnalytics {
  attempts_by_day: AdminAttemptDay[]
  type_accuracy: AdminTypeAccuracy[]
  vocabulary_by_day: AdminVocabularyDay[]
}

// ---- Admin Pro (Spec H) ----

export interface AdminUserPaper { id: string; title: string; generated_at: string; question_count: number }
export interface AdminUserPaperList { items: AdminUserPaper[] }
export interface AdminUserAttempt {
  attempt_id: string
  paper_title: string
  answered_at: string
  item_total: number
  item_correct: number
  correct_rate: number | null
}
export interface AdminUserAttemptList { items: AdminUserAttempt[] }

export interface QuestionBankTypeStat { question_type: string; count: number }
export interface QuestionBankKpStat { knowledge_point_id: string; level1: string; level2: string; count: number }
export interface QuestionBankChapterStat { book: string; chapter_l1: string; chapter_l2: string; count: number }
export interface QuestionBankStats {
  total: number
  by_type: QuestionBankTypeStat[]
  by_knowledge_point: QuestionBankKpStat[]
  by_chapter: QuestionBankChapterStat[]
}
export interface QuestionBankListItem {
  id: string
  question_type: string
  book: string
  chapter_l1: string
  chapter_l2: string
  stem: string
  options: Array<Record<string, unknown>> | null
  answer: unknown
  knowledge_point_ids: string[]
}
export interface QuestionBankList { items: QuestionBankListItem[]; total: number }

export interface AdminRevenueDayPoint { day: string; cents: number }
export interface AdminPackRevenue { pack_id: string; orders: number; cents: number }
export interface AdminRevenue {
  total_cents: number
  revenue_by_day: AdminRevenueDayPoint[]
  by_pack: AdminPackRevenue[]
}

export interface AdminAuditItem {
  id: number
  actor_user_id: string
  actor_username: string | null
  action: string
  target_user_id: string | null
  target_username: string | null
  detail: Record<string, unknown> | null
  created_at: string
}
export interface AdminAuditList { items: AdminAuditItem[]; total: number }

export interface AdminSystemHealth {
  llm: boolean
  /** 后端是否处于离线 mock 支付模式 */
  payment_mock: boolean
  question_bank_total: number
  app_db_size_kb: number
}
