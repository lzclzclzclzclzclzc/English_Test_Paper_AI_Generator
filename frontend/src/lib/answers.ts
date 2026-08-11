import type {
  AnswerValue,
  GradeSubmissionItem,
  Paper,
  PaperItem,
  UserAnswerValue,
} from '@/types/api'

/** 做题中暂存的单题草稿：单选存 label 字符串；填空/改写恒存 blankN 字典。 */
export type BlankMap = Record<string, string>
export type AnswerDraft = string | BlankMap

/** 题干/模板中的"空位"视觉标记：连续 2 个及以上下划线。 */
const BLANK_RUN = /_{2,}/g

const numericSuffix = (key: string) => {
  const m = /(\d+)$/.exec(key)
  return m ? Number(m[1]) : Number.MAX_SAFE_INTEGER
}

/** blank 键按数字后缀排序（防字典序 blank10 < blank2）。 */
const sortBlankKeys = (keys: string[]) =>
  [...keys].sort((a, b) => numericSuffix(a) - numericSuffix(b))

/**
 * 一道题要渲染几个输入框、键名是什么。
 * 兼容两种空位数组形态：
 *   - 单元素多键：                    [{blank1, blank2, blank3}]   （改写/词形/听力填词）
 *   - 多元素单键（每空一个 dict）：    [{blank1},{blank2},{blank3}] （阅读首字母填空）
 * 汇总所有元素的键集，去重后按数字后缀排序。
 * 题干下划线连串数不可靠（真题 220 道中 51 道对不上），绝不据其计数。
 * 单选（answer 为字符串）返回 []；异常数据兜底为单空 ['blank1']。
 */
export function getBlankKeys(answer: AnswerValue): string[] {
  if (typeof answer === 'string') return []
  const keys: string[] = []
  for (const item of answer) {
    if (item && typeof item === 'object') {
      keys.push(...Object.keys(item))
    }
  }
  const unique = [...new Set(keys)]
  return unique.length > 0 ? sortBlankKeys(unique) : ['blank1']
}

/** blankN → "空N"；非标准键名原样显示。 */
export const blankLabel = (key: string) => {
  const m = /^blank(\d+)$/.exec(key)
  return m ? `空${m[1]}` : key
}

/**
 * 按下划线连串切分文本。恰好切出 n 段空位时返回 n+1 个文字片段
 * （空位在片段之间），否则返回 null——调用方回退为"模板原样 + 下方标签输入框"。
 */
export function splitTemplateByBlanks(text: string, n: number): string[] | null {
  const parts = text.split(BLANK_RUN)
  return parts.length === n + 1 ? parts : null
}

const isBlankQuestion = (item: PaperItem) => {
  const qt = item.question.question_type
  // Writing questions are answered with a string essay, not blanks
  if (qt === 'writing') return false
  return typeof item.question.answer !== 'string'
}

/** 单题草稿是否"已答完"：单选有值；填空每个空都非空白。 */
function isDraftComplete(item: PaperItem, draft: AnswerDraft | undefined): boolean {
  if (!isBlankQuestion(item)) {
    return typeof draft === 'string' && draft !== ''
  }
  const keys = getBlankKeys(item.question.answer)
  if (draft == null || typeof draft === 'string') return false
  return keys.every((k) => (draft[k] ?? '').trim() !== '')
}

/** 未作答/未填满的题号列表（提交前确认用）。 */
export function listUnanswered(
  paper: Paper,
  answers: Record<number, AnswerDraft>,
): number[] {
  return paper.items
    .filter((item) => !isDraftComplete(item, answers[item.index]))
    .map((item) => item.index)
}

/**
 * 组装提交体：为试卷**全部** index 各生成恰好一条（后端 422 硬约束）。
 * 单选未答补 ""；填空缺失的键补 ""（空答案判错，但契约必须满足）。
 */
export function buildSubmission(
  paper: Paper,
  answers: Record<number, AnswerDraft>,
): GradeSubmissionItem[] {
  return paper.items.map((item) => {
    const draft = answers[item.index]
    if (!isBlankQuestion(item)) {
      return { index: item.index, user_answer: typeof draft === 'string' ? draft : '' }
    }
    const keys = getBlankKeys(item.question.answer)
    const map: BlankMap = {}
    for (const k of keys) {
      map[k] = (typeof draft === 'object' ? (draft[k] ?? '') : '').trim()
    }
    return { index: item.index, user_answer: map }
  })
}

/** answering 草稿或 review 用户答案 → BlankMap（review 时兼容数组/字符串形态）。 */
export function toBlankMap(
  blankKeys: string[],
  raw: string | string[] | Record<string, string> | undefined,
): BlankMap {
  if (raw == null) return {}
  if (typeof raw === 'string') {
    const first = blankKeys[0]
    return first !== undefined ? { [first]: raw } : {}
  }
  if (Array.isArray(raw)) {
    const map: BlankMap = {}
    raw.forEach((v, i) => {
      const key = blankKeys[i]
      if (key !== undefined) map[key] = v
    })
    return map
  }
  return raw
}

const CIRCLED = ['①', '②', '③', '④', '⑤', '⑥', '⑦', '⑧', '⑨', '⑩'] as const

/** 用户答案 → 人类可读（成绩视图）。空答案显示"（未作答）"。 */
export function formatUserAnswer(v: UserAnswerValue): string {
  if (typeof v === 'string') return v.trim() === '' ? '（未作答）' : v
  if (Array.isArray(v)) {
    const joined = v.filter((s) => s.trim() !== '').join('；')
    return joined === '' ? '（未作答）' : joined
  }
  const keys = sortBlankKeys(Object.keys(v))
  const parts = keys
    .map((k) => (v[k] ?? '').trim())
    .filter((s) => s !== '')
  if (parts.length === 0) return '（未作答）'
  if (keys.length === 1) return parts.join('；')
  return keys.map((k) => `${blankLabel(k)}: ${(v[k] ?? '').trim() || '（空）'}`).join('；')
}

/**
 * 正确答案 → 人类可读：
 * - "B" → "B"
 * - [{blank1:['in','into'], blank2:['order']}] → "空1: in / into；空2: order"
 * - 多候选组合 → "① …　② …"（组合间为"或"的关系）
 */
export function formatCorrectAnswer(a: AnswerValue): string {
  if (typeof a === 'string') return a
  const formatCandidate = (cand: Record<string, string[]>) => {
    const keys = sortBlankKeys(Object.keys(cand))
    if (keys.length === 1) {
      const only = keys[0]
      return (only !== undefined ? (cand[only] ?? []) : []).join(' / ')
    }
    return keys.map((k) => `${blankLabel(k)}: ${(cand[k] ?? []).join(' / ')}`).join('；')
  }
  // 阅读首字母填空：每个元素都是单空 dict（[{blank1},{blank2},…]）→ 按空位顺序展示
  if (a.length > 1 && a.every((c) => c && Object.keys(c).length === 1)) {
    return a
      .map((cand) => {
        const k = Object.keys(cand)[0]
        return k === undefined ? '' : `${blankLabel(k)}: ${(cand[k] ?? []).join(' / ')}`
      })
      .filter(Boolean)
      .join('；')
  }
  if (a.length === 1 && a[0] !== undefined) return formatCandidate(a[0])
  return a
    .map((cand, i) => `${CIRCLED[i] ?? `(${i + 1})`} ${formatCandidate(cand)}`)
    .join('　')
}
