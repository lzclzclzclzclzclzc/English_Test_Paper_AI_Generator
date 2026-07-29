import type {
  GradeResultItem,
  Paper,
  RevisedQuestion,
  RevisionMode,
  UserAnswerValue,
  WrongItemRef,
} from '@/types/api'

/**
 * 错题本（按用户存 localStorage）。
 *
 * 后端只写不读：attempts/attempt_items 落库但没有任何读取端点，对外仅有
 * 聚合的掌握度画像（Spec D § MVP 也明确不持久化 wrong_items）。
 * 所以错题明细只能在交卷判分的瞬间由前端截存——那一刻内存里同时有
 * 完整 Paper（题体）和判分结果（用户答案）。仅本设备有效。
 */

export interface WrongBookEntry {
  /** 题库源题 id——去重键 */
  sourceQuestionId: string
  /** 完整题体（含 answer/solution/knowledge_point_ids），可独立重渲染 */
  question: RevisedQuestion
  /** 请求解析（POST /solutions）时需要 */
  revisionMode: RevisionMode
  paperId: string
  paperTitle: string
  /** ISO 时间戳（判分时刻） */
  gradedAt: string
  /** 当时提交的错误答案 */
  userAnswer: UserAnswerValue
  /** 累计答错次数（再错 +1，答对清账移出） */
  timesWrong: number
}

interface WrongBook {
  version: 1
  entries: WrongBookEntry[]
}

const MAX_ENTRIES = 100
const keyOf = (userId: string) => `mj.wrongbook.v1.${userId}`

function load(userId: string): WrongBook {
  const raw = localStorage.getItem(keyOf(userId))
  if (raw) {
    try {
      const parsed = JSON.parse(raw) as WrongBook
      if (parsed.version === 1 && Array.isArray(parsed.entries)) return parsed
    } catch {
      // 坏数据视为空本
    }
  }
  return { version: 1, entries: [] }
}

/** 超限时减半重试一次，仍失败静默放弃——绝不让交卷流程因错题本崩掉。 */
function save(userId: string, book: WrongBook): void {
  try {
    localStorage.setItem(keyOf(userId), JSON.stringify(book))
  } catch {
    try {
      book.entries = book.entries.slice(0, Math.floor(book.entries.length / 2))
      localStorage.setItem(keyOf(userId), JSON.stringify(book))
    } catch {
      /* 放弃 */
    }
  }
}

export function loadWrongBook(userId: string): WrongBookEntry[] {
  return load(userId).entries
}

/**
 * 交卷判分后记账：本次答错的题收进来（同源题去重、次数累加、最新在前），
 * 本次答对的题从本子里移出（重做答对即清账）。
 */
export function recordGrade(userId: string, paper: Paper, results: GradeResultItem[]): void {
  try {
    const book = load(userId)
    const byIndex = new Map(paper.items.map((item) => [item.index, item]))
    const gradedAt = new Date().toISOString()

    const settled = new Set<string>()
    const fresh: WrongBookEntry[] = []
    for (const r of results) {
      const item = byIndex.get(r.index)
      if (!item) continue
      if (r.is_correct) {
        settled.add(item.source_question_id)
        continue
      }
      const prev = book.entries.find((e) => e.sourceQuestionId === item.source_question_id)
      fresh.push({
        sourceQuestionId: item.source_question_id,
        question: item.question,
        revisionMode: item.revision_mode,
        paperId: paper.paper_id,
        paperTitle: paper.title,
        gradedAt,
        userAnswer: r.user_answer,
        timesWrong: (prev?.timesWrong ?? 0) + 1,
      })
    }

    const freshIds = new Set(fresh.map((e) => e.sourceQuestionId))
    const kept = book.entries.filter(
      (e) => !freshIds.has(e.sourceQuestionId) && !settled.has(e.sourceQuestionId),
    )
    book.entries = [...fresh, ...kept].slice(0, MAX_ENTRIES)
    save(userId, book)
    // 旧的单次错题键已被错题本取代，顺手清理
    localStorage.removeItem(`mj.lastwrong.${userId}`)
  } catch {
    /* 记账失败不影响交卷 */
  }
}

/** 移出一条，返回更新后的列表（供组件同步 state）。 */
export function removeEntry(userId: string, sourceQuestionId: string): WrongBookEntry[] {
  const book = load(userId)
  book.entries = book.entries.filter((e) => e.sourceQuestionId !== sourceQuestionId)
  save(userId, book)
  return book.entries
}

/** 错题条目 → remediation 请求体的 wrong_items。 */
export function toWrongItemRefs(entries: WrongBookEntry[]): WrongItemRef[] {
  return entries.map((e) => ({
    knowledge_point_ids: e.question.knowledge_point_ids,
    question_type: e.question.question_type,
  }))
}
