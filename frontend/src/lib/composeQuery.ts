import type { QuestionType, RevisionMode } from '@/types/api'
import { TYPE_LABELS } from '@/lib/kp'

/**
 * 拼句器:把结构化的出题选择确定性地拼成一句中文 user_query。
 * 措辞逐条对齐 ai_engine/prompts/parser.md 的触发词与 few-shot:
 * - light(默认)开头「来 N 道X」= 示例 1 原句式;
 * - fresh 开头「帮我重新出」= 示例 6(避开「帮我出/来几道」等 light 触发词);
 * - original 后缀「全部用真题原题，不要改」命中最高优先级触发词;
 * - 主题词按规则必然触发 fresh(情境描述),故 topic 非空时自动升档,
 *   original 档与主题互斥(parser 会忽略主题,这里主动丢弃并告警)。
 * - KP 用「和」连接——顿号是分段符,不能混用。
 */

export type Intensity = RevisionMode

/** 与 ai_engine/parser.py MAX_QUESTIONS 对齐 */
export const MAX_QUESTIONS = 31

export interface ComposeEntry {
  type: QuestionType
  /** 数量;单位由 unitOf(type) 决定(散题=道,篇章=篇) */
  count: number
  /** 知识点 level2 中文名(Parser 靠名称/alias 识别);仅语法三类拼入句中 */
  kps?: string[]
}

export interface ComposeInput {
  entries: ComposeEntry[]
  /** 缺省 'light';topic 非空时自动升为 'fresh' */
  intensity?: Intensity
  /** 主题词(如「环保」),仅语法三类走向量检索时有意义 */
  topic?: string
}

/** 按「篇」计数的题型 → 每篇折算题数(parser.md「篇→题」规则) */
const QUESTIONS_PER_PIECE: Partial<Record<QuestionType, number>> = {
  reading_longtext_single_choice: 6,
  cloze_single_choice: 6,
  reading_first_blank: 1, // 1 篇 = 1 题(7 空)
}

const GRAMMAR_TYPES: ReadonlySet<QuestionType> = new Set([
  'single_choice',
  'word_form',
  'sentence_rewriting',
])

export function unitOf(type: QuestionType): '道' | '篇' {
  return type in QUESTIONS_PER_PIECE ? '篇' : '道'
}

export function questionsPerUnit(type: QuestionType): number {
  return QUESTIONS_PER_PIECE[type] ?? 1
}

/** 折算后的总题数(篇 × 每篇题数;reading_first_blank 1 篇计 1 题) */
export function totalQuestions(entries: ComposeEntry[]): number {
  return entries.reduce((sum, e) => sum + e.count * questionsPerUnit(e.type), 0)
}

export interface ComposeIssue {
  level: 'error' | 'warn'
  code: 'empty' | 'count_invalid' | 'over_cap' | 'topic_dropped' | 'topic_fresh'
  message: string
}

/** topic 非空会把 light 升为 fresh;original 优先级最高,不受 topic 影响。 */
function effectiveIntensity(input: ComposeInput): Intensity {
  const base = input.intensity ?? 'light'
  if (base === 'original') return 'original'
  if (input.topic?.trim()) return 'fresh'
  return base
}

/**
 * 校验拼句输入。error 级存在时调用方应阻止提交;本函数不抛错。
 * 薄尾 KP 预警不在这层(拼句只见中文名,题量审计按 id,见 drillConfig.THIN_KP_IDS)。
 */
export function validateCompose(input: ComposeInput): ComposeIssue[] {
  const issues: ComposeIssue[] = []
  const active = input.entries.filter((e) => e.count !== 0)

  if (active.length === 0) {
    issues.push({ level: 'error', code: 'empty', message: '先选择题型和数量' })
    return issues
  }
  for (const e of active) {
    if (!Number.isInteger(e.count) || e.count < 0) {
      issues.push({
        level: 'error',
        code: 'count_invalid',
        message: `${TYPE_LABELS[e.type] ?? e.type} 的数量必须是正整数`,
      })
    }
  }
  const total = totalQuestions(active)
  if (total > MAX_QUESTIONS) {
    issues.push({
      level: 'error',
      code: 'over_cap',
      message: `折算共 ${total} 题，超过单卷上限 ${MAX_QUESTIONS} 题`,
    })
  }
  if (input.topic?.trim()) {
    if ((input.intensity ?? 'light') === 'original') {
      issues.push({
        level: 'warn',
        code: 'topic_dropped',
        message: '真题原样模式下主题词不生效，已忽略',
      })
    } else if ((input.intensity ?? 'light') === 'light') {
      issues.push({
        level: 'warn',
        code: 'topic_fresh',
        message: '指定主题后将全新命题（AI 原创）',
      })
    }
  }
  return issues
}

/** 确定性拼句。调用方需先用 validateCompose 拦下 error 级输入。 */
export function composeQuery(input: ComposeInput): string {
  const intensity = effectiveIntensity(input)
  const topic = input.topic?.trim() ?? ''

  const segments = input.entries
    .filter((e) => e.count > 0)
    .map((e) => {
      const kpPrefix =
        GRAMMAR_TYPES.has(e.type) && e.kps && e.kps.length > 0
          ? `${e.kps.join('和')}的`
          : ''
      return `${e.count} ${unitOf(e.type)}${kpPrefix}${TYPE_LABELS[e.type] ?? e.type}`
    })

  const opening = intensity === 'fresh' ? '帮我重新出 ' : '来 '
  let query = opening + segments.join('、')

  if (intensity === 'original') query += '，全部用真题原题，不要改'
  else if (intensity === 'fresh') query += '，要全新原创的题目'

  if (topic !== '' && intensity !== 'original') query += `，主题关于${topic}`

  return query
}
