import { useState } from 'react'
import { cn } from '@/lib/utils'
import { PageHeader } from '@/components/PageHeader'
import { PipelineProgress } from '@/components/PipelineProgress'
import { MemberPill, UpgradeDialog } from '@/components/UpgradeDialog'
import { useGeneratePaper } from '@/hooks/useGeneratePaper'
import {
  composeQuery,
  totalQuestions,
  type ComposeEntry,
  type Intensity,
} from '@/lib/composeQuery'
import { generateQuotaNotice } from '@/lib/quota'
import { setPendingTimer } from '@/lib/paperTimer'

/** 非会员点「真题检测卷」时的升级文案（与 IntensityPicker 的 original 档一致） */
const ORIGINAL_LOCK_REASON = '真题原卷是会员功能：整卷使用中考真题原题，不做改动。'

interface MockRecipe {
  id: string
  name: string
  /** 结构摘要（quiet 小字） */
  structure: string
  /** 建议用时，也是限时 toggle 的分钟数 */
  minutes: number
  entries: ComposeEntry[]
  /** 缺省 light；'original' = 真题检测卷（会员） */
  intensity?: Intensity
}

/** 全科检测卷结构（配方 1 与配方 5 共用）：折算 2+2+2+6+3+3+6+6 = 30 题 */
const FULL_EXAM_ENTRIES: ComposeEntry[] = [
  { type: 'listening_single_choice', count: 2 },
  { type: 'listening_true_false', count: 2 },
  { type: 'listening_fill_blank', count: 2 },
  { type: 'single_choice', count: 6 },
  { type: 'word_form', count: 3 },
  { type: 'sentence_rewriting', count: 3 },
  { type: 'cloze_single_choice', count: 1 },
  { type: 'reading_longtext_single_choice', count: 1 },
]

/**
 * 5 个配方常量。折算题数（每篇完形/阅读 = 6 题，首字母 1 篇 = 1 题）：
 * 全科 30 / 语法 25 / 听力 15 / 阅读 13 / 真题 30，全部 ≤ MAX_QUESTIONS(30)。
 */
const MOCK_RECIPES: MockRecipe[] = [
  {
    id: 'full',
    name: '全科检测卷',
    structure: '听力 2+2+2 · 单选 6 · 词形 3 · 句改 3 · 完形 1 篇 · 阅读 1 篇',
    minutes: 40,
    entries: FULL_EXAM_ENTRIES,
  },
  {
    id: 'grammar',
    name: '语法强化卷',
    structure: '单选 14 · 词形 6 · 句改 5',
    minutes: 25,
    entries: [
      { type: 'single_choice', count: 14 },
      { type: 'word_form', count: 6 },
      { type: 'sentence_rewriting', count: 5 },
    ],
  },
  {
    id: 'listening',
    name: '听力专场卷',
    structure: '听选 5 · 听判 5 · 听填 5',
    minutes: 15,
    entries: [
      { type: 'listening_single_choice', count: 5 },
      { type: 'listening_true_false', count: 5 },
      { type: 'listening_fill_blank', count: 5 },
    ],
  },
  {
    id: 'reading',
    name: '阅读专场卷',
    structure: '完形 1 篇 · 阅读 1 篇 · 首字母 1 篇',
    minutes: 30,
    entries: [
      { type: 'cloze_single_choice', count: 1 },
      { type: 'reading_longtext_single_choice', count: 1 },
      { type: 'reading_first_blank', count: 1 },
    ],
  },
  {
    id: 'original',
    name: '真题检测卷',
    structure: '同全科检测卷 · 全部使用中考真题原题',
    minutes: 40,
    entries: FULL_EXAM_ENTRIES,
    intensity: 'original',
  },
]

/**
 * 整卷模拟：5 个固定配方一键出卷，可选限时（sessionStorage 交接给试卷页，
 * 到点提醒不强制收卷）。真题检测卷 = 全科配方 + original 强度（会员）。
 */
export function MockPage() {
  const [timed, setTimed] = useState<Record<string, boolean>>({})
  const [serverError, setServerError] = useState<string | null>(null)
  const [upgradeReason, setUpgradeReason] = useState<string | null>(null)

  const { generate, guard, isPending, locked, freeRemaining } = useGeneratePaper(setServerError)
  const quotaNotice = generateQuotaNotice(locked, freeRemaining)

  const start = (recipe: MockRecipe) => {
    setServerError(null)
    // 真题卷先做会员判断，再走免费次数门槛
    if (recipe.intensity === 'original' && locked) {
      setUpgradeReason(ORIGINAL_LOCK_REASON)
      return
    }
    const reason = guard('fresh')
    if (reason) {
      setUpgradeReason(reason)
      return
    }
    if (timed[recipe.id]) setPendingTimer(recipe.minutes)
    generate({
      user_query: composeQuery({ entries: recipe.entries, intensity: recipe.intensity ?? 'light' }),
      mode: 'fresh',
    })
  }

  return (
    <div className="max-w-[56rem]">
      <PageHeader
        title="整卷模拟"
        intro="一键出一份结构完整的检测卷——可选限时，到点提醒不强制收卷。"
      />

      <div className="flex flex-col gap-8">
        <div className="divide-y divide-ink-10 border-y border-hairline">
          {MOCK_RECIPES.map((recipe) => {
            const total = totalQuestions(recipe.entries)
            const isTimed = timed[recipe.id] === true
            return (
              <div
                key={recipe.id}
                className="flex flex-wrap items-center gap-x-8 gap-y-3 px-2 py-5"
              >
                <div className="flex min-w-0 flex-1 basis-[22rem] flex-col gap-1">
                  <div className="flex items-center gap-2">
                    <span className="text-[15.5px] text-ink">{recipe.name}</span>
                    {recipe.intensity === 'original' && <MemberPill />}
                  </div>
                  <span className="text-[12.5px] leading-relaxed text-quiet">
                    {recipe.structure}
                  </span>
                  <span className="font-ui text-[12.5px] tabular-nums text-quiet">
                    {total} 题 · 建议 {recipe.minutes} 分钟
                  </span>
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  <button
                    type="button"
                    aria-pressed={isTimed}
                    className={cn(
                      'rounded-sm border px-3 py-1.5 font-ui text-[12.5px] tabular-nums transition-colors',
                      isTimed
                        ? 'border-accent bg-wash text-accent'
                        : 'border-hairline text-muted-ink hover:border-accent hover:text-accent',
                    )}
                    onClick={() => setTimed((prev) => ({ ...prev, [recipe.id]: !isTimed }))}
                  >
                    限时 {recipe.minutes} 分钟
                  </button>
                  <button
                    type="button"
                    disabled={isPending}
                    className="rounded-sm border border-accent bg-wash px-6 py-1.5 font-ui text-[13.5px] tracking-[0.05em] text-ink transition-colors hover:text-accent disabled:pointer-events-none disabled:opacity-60"
                    onClick={() => start(recipe)}
                  >
                    {isPending ? '生成中…' : '开始'}
                  </button>
                </div>
              </div>
            )
          })}
        </div>

        {serverError && <p className="text-[12px] text-accent">{serverError}</p>}
        {quotaNotice && <p className="text-[12px] text-quiet">{quotaNotice}</p>}

        {isPending && <PipelineProgress />}

        <p className="text-[12.5px] text-quiet">
          模拟卷基于真题库组卷，不含写作；听力为语音朗读。
        </p>
      </div>

      <UpgradeDialog reason={upgradeReason} onClose={() => setUpgradeReason(null)} />
    </div>
  )
}
