import { totalQuestions, unitOf, type ComposeEntry } from '@/lib/composeQuery'
import { TYPE_LABELS } from '@/lib/kp'
import type { KnowledgePoint, MasteryProfile } from '@/types/api'

/**
 * 每日一练配方(纯数据与纯函数,自 components/dashboard/DailyPlan.tsx 抽出):
 * 工作台「今日一练」卡与 /daily 每日一练页共用这一份事实来源。
 */
export interface DailyRecipe {
  name: string
  minutes: number
  entries: ComposeEntry[]
}

/** 周一语法日——也是周日弱点日无掌握度数据时的回退配方 */
export const GRAMMAR_DAY: DailyRecipe = {
  name: '语法日',
  minutes: 12,
  entries: [
    { type: 'single_choice', count: 6 },
    { type: 'word_form', count: 4 },
  ],
}

/**
 * 按星期轮换的固定配方(getDay():0 = 周日)。
 * 周日弱点日不在表里——由 resolveRecipe 按掌握度动态生成。
 */
export const WEEK_RECIPES: Record<number, DailyRecipe> = {
  1: GRAMMAR_DAY,
  2: {
    name: '听力日',
    minutes: 15,
    entries: [
      { type: 'listening_single_choice', count: 3 },
      { type: 'listening_true_false', count: 4 },
      { type: 'listening_fill_blank', count: 3 },
    ],
  },
  3: {
    name: '阅读日',
    minutes: 20,
    entries: [
      { type: 'cloze_single_choice', count: 1 },
      { type: 'reading_longtext_single_choice', count: 1 },
    ],
  },
  4: {
    name: '语法混合',
    minutes: 12,
    entries: [
      { type: 'single_choice', count: 4 },
      { type: 'sentence_rewriting', count: 3 },
      { type: 'word_form', count: 3 },
    ],
  },
  5: {
    name: '综合日',
    minutes: 15,
    entries: [
      { type: 'single_choice', count: 3 },
      { type: 'word_form', count: 2 },
      { type: 'sentence_rewriting', count: 2 },
      { type: 'listening_single_choice', count: 3 },
    ],
  },
  6: {
    name: '阅读强化',
    minutes: 20,
    entries: [
      { type: 'reading_longtext_single_choice', count: 1 },
      { type: 'reading_first_blank', count: 1 },
    ],
  },
}

/** 周日的占位名(动态配方,列表展示用) */
export const SUNDAY_NAME = '弱点日'

/**
 * 解析某个星期几的配方。周日弱点日:近 30 天最弱 2 个考点各出 5 道
 * 对应题型(KP 的 level1);无掌握度数据 / 目录未到时退回语法日配方。
 */
export function resolveRecipe(
  weekday: number,
  mastery: MasteryProfile | undefined,
  catalog: KnowledgePoint[] | undefined,
): DailyRecipe {
  if (weekday !== 0) return WEEK_RECIPES[weekday] ?? GRAMMAR_DAY

  const weakest = [...(mastery?.weak_kps ?? [])].sort((a, b) => a.mastery - b.mastery)
  const entries: ComposeEntry[] = []
  for (const kp of weakest) {
    const cat = catalog?.find((c) => c.id === kp.knowledge_point_id)
    if (!cat) continue
    entries.push({ type: cat.level1, count: 5, kps: [cat.level2] })
    if (entries.length === 2) break
  }
  if (entries.length === 0) return GRAMMAR_DAY
  return { name: SUNDAY_NAME, minutes: 12, entries }
}

/** 结构摘要:「单项选择 6 道 + 词形转换 4 道」;弱点日带上考点名 */
export function structureOf(entries: ComposeEntry[]): string {
  return entries
    .map((e) => {
      const typeLabel = TYPE_LABELS[e.type] ?? e.type
      const label = e.kps && e.kps.length > 0 ? `${e.kps.join('、')}·${typeLabel}` : typeLabel
      return `${label} ${e.count} ${unitOf(e.type)}`
    })
    .join(' + ')
}

export function recipeTotal(recipe: DailyRecipe): number {
  return totalQuestions(recipe.entries)
}

const pad = (n: number) => String(n).padStart(2, '0')

/** 本地时区 YYYY-MM-DD */
export const localDay = (d = new Date()) =>
  `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`

/** 「今天练过」的 localStorage 键(存在即视为练过;不存 paper_id,不做打卡链) */
export const dailyDoneKey = (userId: string) => `mj.daily.${userId}.${localDay()}`

/** 周一起序的星期名与 getDay() 值(每日一练页的一周安排表用) */
export const WEEKDAYS: readonly { day: number; label: string }[] = [
  { day: 1, label: '周一' },
  { day: 2, label: '周二' },
  { day: 3, label: '周三' },
  { day: 4, label: '周四' },
  { day: 5, label: '周五' },
  { day: 6, label: '周六' },
  { day: 0, label: '周日' },
]
