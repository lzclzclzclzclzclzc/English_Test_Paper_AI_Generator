import { useState } from 'react'
import { Link } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { PageHeader } from '@/components/PageHeader'
import { PipelineProgress } from '@/components/PipelineProgress'
import { UpgradeDialog } from '@/components/UpgradeDialog'
import { useGeneratePaper } from '@/hooks/useGeneratePaper'
import { composeQuery } from '@/lib/composeQuery'
import { DRILL_FAMILIES } from '@/lib/drillConfig'
import { FAMILY_LABELS, FAMILY_TEXT_CLASS, TYPE_LABELS, type TypeFamily } from '@/lib/kp'
import { generateQuotaNotice } from '@/lib/quota'
import { PATHS } from '@/lib/paths'
import type { QuestionType } from '@/types/api'

/** 族色细线（border-b 30% 不透明度）——Tailwind 需要写死类名 */
const FAMILY_BORDER_CLASS: Record<TypeFamily, string> = {
  grammar: 'border-grammar/30',
  listening: 'border-listening/30',
  reading: 'border-reading/30',
}

const FAMILY_DESC: Record<TypeFamily, string> = {
  grammar: '打牢语法基本功，三类题占中考笔试大头',
  listening: 'AI 朗读，可反复听',
  reading: '长文、完形与首字母，按篇成组',
}

/** 主题出卷的场景 chips（比专项页多美食/友谊两个泛用话题） */
const THEME_SCENES = ['校园生活', '环保', '科技', '运动', '节日', '旅行', '美食', '友谊'] as const

/** 主题出卷只开语法三类（篇章题型 SQL 随机，主题词无效） */
const THEME_TYPES: readonly QuestionType[] = ['single_choice', 'word_form', 'sentence_rewriting']

const THEME_COUNTS = [8, 10, 12] as const

/** 速练一组：单题型 5 道，默认强度（light），点击即出 */
const QUICK_SETS: ReadonlyArray<{ label: string; type: QuestionType }> = [
  { label: '5 道单项选择', type: 'single_choice' },
  { label: '5 道词形转换', type: 'word_form' },
  { label: '5 道句子改写', type: 'sentence_rewriting' },
]

const chipClass = (selected: boolean) =>
  cn(
    'rounded-sm border px-3 py-1 font-ui text-[12.5px] transition-colors',
    selected
      ? 'border-accent bg-wash text-accent'
      : 'border-hairline text-muted-ink hover:border-accent hover:text-accent',
  )

/**
 * 练习中心 hub：九大题型按语法/听力/阅读三族分区（行式，非卡片），
 * 外加主题出卷、速练一组两个快捷通道与自选组卷入口。
 */
export function PracticePage() {
  const [theme, setTheme] = useState<string | null>(null)
  const [themeType, setThemeType] = useState<QuestionType>('single_choice')
  const [themeCount, setThemeCount] = useState<number>(10)
  const [serverError, setServerError] = useState<string | null>(null)
  const [upgradeReason, setUpgradeReason] = useState<string | null>(null)

  const { generate, guard, isPending, locked, freeRemaining } = useGeneratePaper(setServerError)
  const quotaNotice = generateQuotaNotice(locked, freeRemaining)

  /** guard('fresh') → 拼句 → 出卷（主题出卷与速练一组共用） */
  const submit = (type: QuestionType, count: number, topic?: string) => {
    setServerError(null)
    const reason = guard('fresh')
    if (reason) {
      setUpgradeReason(reason)
      return
    }
    generate({
      user_query: composeQuery({ entries: [{ type, count }], topic }),
      mode: 'fresh',
    })
  }

  return (
    <div className="max-w-[56rem]">
      <PageHeader
        title="练习中心"
        intro="九大题型按语法、听力、阅读三科组织——选一类开始专项练习，或去自选组卷混合搭配。"
      />

      <div className="flex flex-col gap-12">
        {/* 三族分区：族标题 + 族色细线 + 行式题型条目 */}
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
            <p className="mt-2.5 text-[13.5px] text-muted-ink">{FAMILY_DESC[family]}</p>
            <div className="mt-1 divide-y divide-ink-10">
              {configs.map((config) => (
                <Link
                  key={config.slug}
                  to={PATHS.practiceType(config.slug)}
                  className="group flex items-baseline gap-4 px-2 py-4 transition-colors hover:bg-tint"
                >
                  <span className="text-[15.5px] text-ink">{config.label}</span>
                  <span className="text-[12.5px] text-quiet">{config.bankLabel}</span>
                  <span className="ml-auto shrink-0 font-ui text-[13px] text-quiet transition-colors group-hover:text-accent">
                    开始 →
                  </span>
                </Link>
              ))}
            </div>
          </section>
        ))}

        {/* 主题出卷条：挑话题 → AI 全新命题（仅语法题型） */}
        <section className="flex flex-col gap-4 border-t border-hairline pt-8">
          <div className="flex flex-col gap-1.5">
            <span className="font-ui text-[11px] font-bold tracking-[0.14em] text-quiet">
              按主题出卷
            </span>
            <p className="text-[13.5px] text-muted-ink">挑一个话题，AI 全新命题（仅语法题型）</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {THEME_SCENES.map((scene) => (
              <button
                key={scene}
                type="button"
                className={chipClass(theme === scene)}
                onClick={() => setTheme(theme === scene ? null : scene)}
              >
                {scene}
              </button>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
            <div className="flex items-center gap-2">
              {THEME_TYPES.map((type) => (
                <button
                  key={type}
                  type="button"
                  className={chipClass(themeType === type)}
                  onClick={() => setThemeType(type)}
                >
                  {TYPE_LABELS[type]}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-2">
              {THEME_COUNTS.map((n) => (
                <button
                  key={n}
                  type="button"
                  className={cn(chipClass(themeCount === n), 'min-w-10 tabular-nums')}
                  onClick={() => setThemeCount(n)}
                >
                  {n} 道
                </button>
              ))}
            </div>
            <button
              type="button"
              disabled={isPending || theme === null}
              className="rounded-sm border border-accent bg-wash px-6 py-1.5 font-ui text-[13.5px] tracking-[0.05em] text-ink transition-colors hover:text-accent disabled:pointer-events-none disabled:opacity-60"
              onClick={() => theme !== null && submit(themeType, themeCount, theme)}
            >
              {isPending ? '生成中…' : '生成'}
            </button>
          </div>
          {serverError && <p className="text-[12px] text-accent">{serverError}</p>}
          {quotaNotice && <p className="font-ui text-[12px] tabular-nums text-quiet">{quotaNotice}</p>}
        </section>

        {/* 速练一组：点击即出，默认强度 */}
        <section className="flex flex-wrap items-center gap-3">
          <span className="font-ui text-[11px] font-bold tracking-[0.14em] text-quiet">
            速练一组
          </span>
          {QUICK_SETS.map(({ label, type }) => (
            <button
              key={type}
              type="button"
              disabled={isPending}
              className="rounded-sm border border-hairline px-3 py-1 font-ui text-[12.5px] text-muted-ink transition-colors hover:border-accent hover:text-accent disabled:pointer-events-none disabled:opacity-60"
              onClick={() => submit(type, 5)}
            >
              {label}
            </button>
          ))}
          <span className="text-[12px] text-quiet">五分钟，来一组</span>
        </section>

        {isPending && <PipelineProgress />}

        {/* 自选组卷入口 + 词汇预告 */}
        <div className="divide-y divide-ink-10 border-t border-hairline">
          <Link
            to={PATHS.practiceCustom}
            className="group flex items-baseline gap-3 px-2 py-5 transition-colors hover:bg-tint"
          >
            <span className="text-[15px] text-ink">自选组卷工坊</span>
            <span className="text-[13.5px] text-muted-ink">
              — 九种题型自由配比，考点、强度、主题一次配好
            </span>
            <span className="ml-auto shrink-0 font-ui text-[13px] text-quiet transition-colors group-hover:text-accent">
              →
            </span>
          </Link>
          <div className="flex flex-wrap items-baseline gap-2 px-2 py-5 text-[13px] text-quiet">
            <span>词汇学习</span>
            <span className="rounded-sm border border-hairline px-1.5 py-px font-ui text-[10.5px] leading-relaxed">
              即将上线
            </span>
            <span>— 国家核心 1600 词，间隔重复安排复习节奏</span>
          </div>
        </div>
      </div>

      <UpgradeDialog reason={upgradeReason} onClose={() => setUpgradeReason(null)} />
    </div>
  )
}
