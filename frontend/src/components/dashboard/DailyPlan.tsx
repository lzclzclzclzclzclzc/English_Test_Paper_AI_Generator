import { useState } from 'react'
import { useKnowledgePoints } from '@/hooks/useKnowledgePoints'
import { totalQuestions, unitOf, type ComposeEntry, type ComposeInput } from '@/lib/composeQuery'
import { TYPE_LABELS } from '@/lib/kp'
import type { KnowledgePoint, MasteryProfile } from '@/types/api'

interface DailyRecipe {
  name: string
  minutes: number
  entries: ComposeEntry[]
}

/** 周一语法日——也是周日弱点日无掌握度数据时的回退配方 */
const GRAMMAR_DAY: DailyRecipe = {
  name: '语法日',
  minutes: 12,
  entries: [
    { type: 'single_choice', count: 6 },
    { type: 'word_form', count: 4 },
  ],
}

/**
 * 按星期轮换的固定配方（getDay()：0 = 周日）。
 * 周日弱点日不在表里——由 resolveTodayRecipe 按掌握度动态生成。
 */
const WEEK_RECIPES: Record<number, DailyRecipe> = {
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

/**
 * 周日弱点日：近 30 天最弱 2 个考点各出 5 道对应题型（KP 的 level1）；
 * 无掌握度数据 / 目录未到时退回语法日配方。
 */
function resolveTodayRecipe(
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
  return { name: '弱点日', minutes: 12, entries }
}

/** 结构摘要：「单项选择 6 道 + 词形转换 4 道」；弱点日带上考点名 */
function structureOf(entries: ComposeEntry[]): string {
  return entries
    .map((e) => {
      const typeLabel = TYPE_LABELS[e.type] ?? e.type
      const label = e.kps && e.kps.length > 0 ? `${e.kps.join('、')}·${typeLabel}` : typeLabel
      return `${label} ${e.count} ${unitOf(e.type)}`
    })
    .join(' + ')
}

const pad = (n: number) => String(n).padStart(2, '0')

const localDay = (d = new Date()) =>
  `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`

interface DailyPlanProps {
  userId: string
  mastery: MasteryProfile | undefined
  isPending: boolean
  /** 返回 true = 已实际发起生成（guard 放行）；false = 被会员/配额拦截 */
  onStart: (input: ComposeInput) => boolean
}

/**
 * 今日一练：按星期轮换的固定配方一键出卷。localStorage 记
 * `mj.daily.{userId}.{YYYY-MM-DD}`——键存在即视为练过（不存 paper_id，
 * 不做打卡链），仍可「再练一组」。
 */
export function DailyPlan({ userId, mastery, isPending, onStart }: DailyPlanProps) {
  const kpQuery = useKnowledgePoints()
  const [, setTick] = useState(0)

  const todayKey = `mj.daily.${userId}.${localDay()}`
  const doneToday = localStorage.getItem(todayKey) !== null

  const recipe = resolveTodayRecipe(new Date().getDay(), mastery, kpQuery.data)
  const total = totalQuestions(recipe.entries)

  const start = () => {
    const started = onStart({ entries: recipe.entries })
    if (started) {
      localStorage.setItem(todayKey, 'pending')
      setTick((t) => t + 1)
    }
  }

  return (
    <section className="flex flex-col gap-3 border-t border-hairline pt-6">
      <span className="font-ui text-[11px] font-bold tracking-[0.14em] text-quiet">
        今日一练 · {recipe.name}
      </span>
      <p className="text-[13.5px] leading-relaxed text-muted-ink">
        {structureOf(recipe.entries)} · 共 {total} 题 · 约 {recipe.minutes} 分钟
      </p>
      <div>
        {doneToday ? (
          <button
            type="button"
            disabled={isPending}
            className="rounded-sm border border-hairline px-5 py-2 font-ui text-[13.5px] text-muted-ink transition-colors hover:border-accent hover:text-accent disabled:pointer-events-none disabled:opacity-60"
            onClick={start}
          >
            {isPending ? '生成中…' : '今天已练过 · 再练一组'}
          </button>
        ) : (
          <button
            type="button"
            disabled={isPending}
            className="rounded-sm border border-accent bg-wash px-6 py-2 font-ui text-[13.5px] tracking-[0.05em] text-ink transition-colors hover:text-accent disabled:pointer-events-none disabled:opacity-60"
            onClick={start}
          >
            {isPending ? '生成中…' : '开始今日一练'}
          </button>
        )}
      </div>
    </section>
  )
}
