import { useState } from 'react'
import { cn } from '@/lib/utils'
import { PageHeader } from '@/components/PageHeader'
import { PipelineProgress } from '@/components/PipelineProgress'
import { CreditHint } from '@/components/CreditHint'
import { IntensityPicker } from '@/components/drill/IntensityPicker'
import { KpPicker } from '@/components/drill/KpPicker'
import { QueryPreview } from '@/components/drill/QueryPreview'
import { TopicInput } from '@/components/drill/TopicInput'
import { useGeneratePaper } from '@/hooks/useGeneratePaper'
import { useKnowledgePoints } from '@/hooks/useKnowledgePoints'
import {
  MAX_QUESTIONS,
  composeQuery,
  questionsPerUnit,
  totalQuestions,
  validateCompose,
  type ComposeEntry,
  type ComposeInput,
  type Intensity,
} from '@/lib/composeQuery'
import { DRILL_CONFIGS, DRILL_FAMILIES, type DrillConfig } from '@/lib/drillConfig'
import { FAMILY_LABELS, FAMILY_TEXT_CLASS, type TypeFamily } from '@/lib/kp'
import { INTENSITY_ACTION } from '@/lib/creditsActions'
import { useCredits } from '@/hooks/useCredits'
import type { QuestionType } from '@/types/api'
import { Button } from '@/components/ui/button'


/** 工坊三档全开（阅读首字母的锁档只在专项页；这里由全局强度统一控制） */
const ALL_TIERS: DrillConfig['intensity'] = { options: ['original', 'light', 'fresh'] }

/** 族色细线（同 PracticePage 手法——Tailwind 需要写死类名） */
const FAMILY_BORDER_CLASS: Record<TypeFamily, string> = {
  grammar: 'border-grammar/30',
  listening: 'border-listening/30',
  reading: 'border-reading/30',
  writing: 'border-writing/30',
}

const GRAMMAR_TYPES: readonly QuestionType[] = ['single_choice', 'word_form', 'sentence_rewriting']

const zeroCounts = () =>
  Object.fromEntries(DRILL_CONFIGS.map((c) => [c.type, 0])) as Record<QuestionType, number>

/** 数量步进（0..max，0 = 不出）：− 数字·单位 + */
function CountStepper({
  value,
  max,
  unit,
  onChange,
}: {
  value: number
  max: number
  unit: '道' | '篇'
  onChange: (n: number) => void
}) {
  const stepBtn =
    'flex size-7 items-center justify-center rounded-sm border border-hairline font-ui text-[15px] leading-none text-muted-ink transition-colors hover:border-accent hover:text-accent disabled:pointer-events-none disabled:opacity-40'
  return (
    <div className="flex shrink-0 items-center gap-2">
      <button
        type="button"
        aria-label="减少数量"
        disabled={value <= 0}
        className={stepBtn}
        onClick={() => onChange(Math.max(0, value - 1))}
      >
        −
      </button>
      <span className="min-w-14 text-center font-ui text-[15px] font-bold tabular-nums text-ink">
        {value === 0 ? (
          <span className="text-[13px] font-normal text-quiet">不出</span>
        ) : (
          <>
            {value} <span className="text-[13px] font-normal text-muted-ink">{unit}</span>
          </>
        )}
      </span>
      <button
        type="button"
        aria-label="增加数量"
        disabled={value >= max}
        className={stepBtn}
        onClick={() => onChange(Math.min(max, value + 1))}
      >
        +
      </button>
    </div>
  )
}

/**
 * 自选组卷工坊：十种题型自由配比（0 = 不出），语法行可各自选考点，
 * 右栏汇总 + 强度/主题/预览——最终仍走 composeQuery 拼句、fresh 通道出卷。
 */
export function CustomPaperPage() {
  const [counts, setCounts] = useState<Record<QuestionType, number>>(zeroCounts)
  const [kpSel, setKpSel] = useState<Partial<Record<QuestionType, string[]>>>({})
  const [kpOpen, setKpOpen] = useState<Partial<Record<QuestionType, boolean>>>({})
  const [intensity, setIntensity] = useState<Intensity>('light')
  const [topic, setTopic] = useState('')
  const [serverError, setServerError] = useState<string | null>(null)

  const { generate, guard, isPending } = useGeneratePaper(setServerError, 'custom')
  const { price } = useCredits()
  const kpQuery = useKnowledgePoints()

  // kp id → level2 中文名（composeQuery 拼句用名称，Parser 靠名称/alias 识别）
  const kpNamesOf = (type: QuestionType): string[] =>
    (kpSel[type] ?? [])
      .map((id) => kpQuery.data?.find((kp) => kp.id === id)?.level2)
      .filter((name): name is string => Boolean(name))

  const activeConfigs = DRILL_CONFIGS.filter((c) => (counts[c.type] ?? 0) > 0)
  const entries: ComposeEntry[] = activeConfigs.map((c) => ({
    type: c.type,
    count: counts[c.type] ?? 0,
    ...(c.supportsKp ? { kps: kpNamesOf(c.type) } : {}),
  }))

  const grammarSum = GRAMMAR_TYPES.reduce((sum, t) => sum + (counts[t] ?? 0), 0)
  const hasFirstBlank = (counts.reading_first_blank ?? 0) > 0
  const total = totalQuestions(entries)

  const input: ComposeInput = {
    entries,
    intensity,
    ...(grammarSum > 0 ? { topic } : {}),
  }
  const hasError = validateCompose(input).some((i) => i.level === 'error')
  // 预估价：语法题带主题会被 composeQuery 升为全新出题
  const effectiveIntensity: Intensity = grammarSum > 0 && topic.trim() ? 'fresh' : intensity
  const estimatedCost = total > 0 ? price(INTENSITY_ACTION[effectiveIntensity], total) : null

  const handleSubmit = () => {
    setServerError(null)
    if (!guard(estimatedCost)) return
    generate({ user_query: composeQuery(input), mode: 'fresh' })
  }

  return (
    <div className="max-w-[64rem]">
      <div className="lg:grid lg:grid-cols-[minmax(0,1fr)_300px] lg:gap-10">
        {/* 左列：页头 + 三族题型行（数量 stepper，语法行可展开选考点） */}
        <div className="min-w-0">
          <PageHeader
            title="自选组卷"
            intro="像点菜一样配一份卷：十种题型自由配比，考点、强度、主题一次配好。"
          />

          <div className="flex flex-col gap-10">
            {DRILL_FAMILIES.map(({ family, configs }) => (
              <section key={family}>
                <div className={cn('border-b pb-2', FAMILY_BORDER_CLASS[family])}>
                  <span
                    className={cn(
                      'font-ui text-[11px] font-bold tracking-[0.14em]',
                      FAMILY_TEXT_CLASS[family],
                    )}
                  >
                    {family.toUpperCase()} · {FAMILY_LABELS[family]}
                  </span>
                </div>
                <div className="divide-y divide-ink-10">
                  {configs.map((config) => {
                    const count = counts[config.type] ?? 0
                    const open = kpOpen[config.type] === true
                    return (
                      <div key={config.type} className="flex flex-col gap-3 px-2 py-4">
                        <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
                          <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                            <span className="text-[15px] text-ink">{config.label}</span>
                            <span className="text-[12px] leading-relaxed text-quiet">
                              {config.bankLabel}
                              {config.unitHint ? ` · ${config.unitHint}` : ''}
                            </span>
                          </div>
                          <CountStepper
                            value={count}
                            max={config.maxCount}
                            unit={config.unit}
                            onChange={(n) =>
                              setCounts((prev) => ({ ...prev, [config.type]: n }))
                            }
                          />
                        </div>
                        {config.supportsKp && count > 0 && (
                          <div className="flex flex-col gap-2">
                            <button
                              type="button"
                              className="self-start font-ui text-[12px] text-muted-ink underline decoration-ink-30 underline-offset-4 transition-colors hover:text-accent"
                              onClick={() =>
                                setKpOpen((prev) => ({ ...prev, [config.type]: !open }))
                              }
                            >
                              {open
                                ? '收起考点'
                                : `选考点（可选${(kpSel[config.type]?.length ?? 0) > 0 ? ` · 已选 ${kpSel[config.type]?.length}` : ''}）`}
                            </button>
                            {open && (
                              <div className="kk-rise">
                                <KpPicker
                                  type={config.type}
                                  value={kpSel[config.type] ?? []}
                                  onChange={(ids) =>
                                    setKpSel((prev) => ({ ...prev, [config.type]: ids }))
                                  }
                                />
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              </section>
            ))}
          </div>
        </div>

        {/* 右列：粘顶汇总栏（工具面板，细线框无阴影；max-lg 置底） */}
        <aside className="mt-12 lg:sticky lg:top-10 lg:mt-0 lg:self-start">
          <div className="flex flex-col gap-6 rounded-md border border-hairline p-5">
            <span className="kicker">
              组卷汇总
            </span>

            {activeConfigs.length === 0 ? (
              <p className="text-[13px] leading-relaxed text-quiet">
                还没有选题——把左侧想要的题型数量调到 1 以上
              </p>
            ) : (
              <div className="flex flex-col divide-y divide-ink-10">
                {activeConfigs.map((c) => {
                  const count = counts[c.type] ?? 0
                  const per = questionsPerUnit(c.type)
                  return (
                    <div key={c.type} className="flex items-baseline justify-between gap-3 py-2">
                      <span className="text-[13.5px] text-ink">{c.label}</span>
                      <span className="shrink-0 font-ui text-[12.5px] tabular-nums text-muted-ink">
                        {count} {c.unit}
                        {per > 1 ? ` = ${count * per} 题` : ''}
                      </span>
                    </div>
                  )
                })}
              </div>
            )}

            <div className="flex items-baseline justify-between border-t border-hairline pt-3">
              <span className="text-[13px] text-muted-ink">合计</span>
              <span
                className={cn(
                  'font-ui text-[15px] font-bold tabular-nums',
                  total > MAX_QUESTIONS ? 'text-accent' : 'text-ink',
                )}
              >
                共 {total} / {MAX_QUESTIONS} 题
              </span>
            </div>

            <IntensityPicker config={ALL_TIERS} value={intensity} onChange={setIntensity} />

            <div className="flex flex-col gap-2">
              <div className={cn(grammarSum === 0 && 'pointer-events-none opacity-50')}>
                <TopicInput
                  value={topic}
                  onChange={setTopic}
                  disabled={intensity === 'original'}
                />
              </div>
              {grammarSum === 0 && (
                <p className="text-[12px] text-quiet">主题仅对语法题生效</p>
              )}
            </div>

            {hasFirstBlank && (
              <p className="text-[12px] text-quiet">首字母篇目固定使用真题原文</p>
            )}

            {entries.length > 0 && <QueryPreview input={input} />}

            <div className="flex flex-col gap-3">
              <Button
                size="lg"
                type="button"
                disabled={isPending || hasError}
                onClick={handleSubmit}
              >
                {isPending ? '生成中…' : '生成试卷'}
              </Button>
              {total > 0 && (
                <CreditHint action={INTENSITY_ACTION[effectiveIntensity]} cost={estimatedCost} prefix="本卷约" />
              )}
              {serverError && <p className="text-[12px] text-accent">{serverError}</p>}
            </div>
          </div>
        </aside>
      </div>

      {isPending && (
        <div className="mt-10">
          <PipelineProgress />
        </div>
      )}
    </div>
  )
}
