import { useState } from 'react'
import { cn } from '@/lib/utils'
import { PageHeader } from '@/components/PageHeader'
import { PipelineProgress } from '@/components/PipelineProgress'
import { CreditHint } from '@/components/CreditHint'
import { useCredits } from '@/hooks/useCredits'
import { useGeneratePaper } from '@/hooks/useGeneratePaper'
import {
  composeQuery,
  totalQuestions,
  type ComposeEntry,
  type Intensity,
} from '@/lib/composeQuery'
import { INTENSITY_ACTION } from '@/lib/creditsActions'
import { setPendingTimer } from '@/lib/paperTimer'
import { Button } from '@/components/ui/button'

interface MockRecipe {
  id: string
  name: string
  /** 结构摘要（quiet 小字） */
  structure: string
  /** 建议用时，也是限时 toggle 的分钟数 */
  minutes: number
  entries: ComposeEntry[]
  /** 缺省 light；'original' = 真题检测卷（按真题原样价计，最便宜） */
  intensity?: Intensity
}

/** 全科检测卷结构（配方 1 与配方 5 共用）：折算 2+5+5+6+3+3+6+6+1 = 37 题 */
const FULL_EXAM_ENTRIES: ComposeEntry[] = [
  { type: 'listening_single_choice', count: 2 },
  { type: 'listening_true_false', count: 1 },
  { type: 'listening_fill_blank', count: 1 },
  { type: 'single_choice', count: 6 },
  { type: 'word_form', count: 3 },
  { type: 'sentence_rewriting', count: 3 },
  { type: 'cloze_single_choice', count: 1 },
  { type: 'reading_longtext_single_choice', count: 1 },
  { type: 'writing', count: 1 },
]

/**
 * 6 个配方常量。折算题数（每篇听判/听填 = 5 题，每篇完形/阅读 = 6 题，首字母 1 篇 = 1 题）：
 * 全科 37 / 语法 25 / 听力 15 / 阅读 13 / 写作 1 / 真题 37，全部 ≤ MAX_QUESTIONS(50)。
 */
const MOCK_RECIPES: MockRecipe[] = [
  {
    id: 'full',
    name: '全科模拟卷',
    structure: '听力 2+1+1 · 单选 6 · 词形 3 · 句改 3 · 完形 1 篇 · 阅读 1 篇 · 作文 1 篇',
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
    structure: '听选 5 · 听判 1 篇 · 听填 1 篇',
    minutes: 15,
    entries: [
      { type: 'listening_single_choice', count: 5 },
      { type: 'listening_true_false', count: 1 },
      { type: 'listening_fill_blank', count: 1 },
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
    id: 'writing',
    name: '写作专场卷',
    structure: '作文 1 篇',
    minutes: 25,
    entries: [{ type: 'writing', count: 1 }],
  },
  {
    id: 'original',
    name: '真题检测卷',
    structure: '同全科模拟卷 · 全部使用中考真题原题',
    minutes: 40,
    entries: FULL_EXAM_ENTRIES,
    intensity: 'original',
  },
]

/**
 * 整卷模拟：6 个固定配方一键出卷，可选限时（sessionStorage 交接给试卷页，
 * 到点提醒不强制收卷）。真题检测卷 = 全科配方 + original 强度。
 */
export function MockPage() {
  const [timed, setTimed] = useState<Record<string, boolean>>({})
  const [serverError, setServerError] = useState<string | null>(null)

  const { generate, guard, isPending } = useGeneratePaper(setServerError)
  const { price } = useCredits()
  const costOf = (recipe: MockRecipe) =>
    price(INTENSITY_ACTION[recipe.intensity ?? 'light'], totalQuestions(recipe.entries))

  const start = (recipe: MockRecipe) => {
    setServerError(null)
    if (!guard(costOf(recipe))) return
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
        <div className="tile-grid" style={{ ['--tile-cols' as string]: '1' }}>
          {MOCK_RECIPES.map((recipe) => {
            const total = totalQuestions(recipe.entries)
            const isTimed = timed[recipe.id] === true
            // 按 recipe.id 精确匹配色调，语义与分科色对齐
            const TONE_BY_ID: Record<string, string> = {
              full: 'tile--accent',
              grammar: 'tile--grammar',
              listening: 'tile--listening',
              reading: 'tile--reading',
              writing: 'tile--writing',
              original: 'tile--accent',
            }
            const tone = TONE_BY_ID[recipe.id] ?? 'tile--accent'
            return (
              <div key={recipe.id} className={cn('tile', tone)}>
                <span className="tile-title">{recipe.name}</span>
                <span className="tile-desc">{recipe.structure}</span>
                <span className="tile-idx mt-0.5 flex items-center gap-2">
                  {total} 题 · 建议 {recipe.minutes} 分钟
                  <CreditHint action={INTENSITY_ACTION[recipe.intensity ?? 'light']} cost={costOf(recipe)} className="font-normal tracking-normal" />
                </span>
                <div className="mt-3 flex items-center gap-2">
                  <button
                    type="button"
                    aria-pressed={isTimed}
                    className="seg seg-sm tabular-nums"
                    onClick={() => setTimed((prev) => ({ ...prev, [recipe.id]: !isTimed }))}
                  >
                    限时 {recipe.minutes} 分钟
                  </button>
                  <Button
                    type="button"
                    disabled={isPending}
                    className="px-5"
                    onClick={() => start(recipe)}
                  >
                    {isPending ? '生成中…' : '开始'}
                  </Button>
                </div>
              </div>
            )
          })}
        </div>

        {serverError && <p className="text-[12px] text-accent">{serverError}</p>}

        {isPending && <PipelineProgress />}

        <p className="text-[12.5px] text-quiet">
          模拟卷基于真题库组卷，含写作（AI 从内容 / 语言 / 组织三维度批改）；听力为语音朗读。
        </p>
      </div>
    </div>
  )
}
