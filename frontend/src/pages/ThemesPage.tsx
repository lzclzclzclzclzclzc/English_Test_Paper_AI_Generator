import { useState } from 'react'
import { Link } from 'react-router-dom'
import { PageHeader } from '@/components/PageHeader'
import { PipelineProgress } from '@/components/PipelineProgress'
import { UpgradeDialog } from '@/components/UpgradeDialog'
import { QueryPreview } from '@/components/drill/QueryPreview'
import { useGeneratePaper } from '@/hooks/useGeneratePaper'
import { composeQuery, validateCompose, type ComposeEntry, type ComposeInput } from '@/lib/composeQuery'
import { TYPE_LABELS } from '@/lib/kp'
import { PATHS } from '@/lib/paths'
import { generateQuotaNotice } from '@/lib/quota'
import { cn } from '@/lib/utils'
import type { QuestionType } from '@/types/api'

/** 场景 chips(单选,与自定义输入互斥) */
const SCENES = ['校园生活', '环保', '科技', '运动', '节日', '旅行', '美食', '友谊'] as const

/** 题型配比行:主题出题仅语法三类(听力/阅读按篇章固定出题,不吃主题词) */
const THEME_TYPES: readonly QuestionType[] = ['single_choice', 'word_form', 'sentence_rewriting']

/** 数量档位(font-ui 分段) */
const COUNT_TIERS = [3, 5, 8] as const

interface RowState {
  enabled: boolean
  count: number
}

/** 勾选方块(同错题本 WrongBookList):选中 = 赤陶边 + wash 底 + ✓。 */
function CheckSquare({
  checked,
  onChange,
  label,
}: {
  checked: boolean
  onChange: () => void
  label: string
}) {
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={checked}
      aria-label={label}
      onClick={onChange}
      className={cn(
        'flex size-[18px] shrink-0 items-center justify-center rounded-sm border font-ui text-[11px] leading-none transition-colors',
        checked
          ? 'border-accent bg-wash text-accent'
          : 'border-ink-20 text-transparent hover:border-ink-30',
      )}
    >
      ✓
    </button>
  )
}

/**
 * 主题出卷:话题 × 语法题型的结合页——选一个场景(或自己写),配上题型
 * 与数量,AI 围绕这个场景全新命题(intensity 固定 fresh)。
 * 出卷范式同 MockPage(guard('fresh') → UpgradeDialog / generate)。
 */
export function ThemesPage() {
  const [scene, setScene] = useState<string | null>(null)
  const [custom, setCustom] = useState('')
  const [rows, setRows] = useState<Record<QuestionType, RowState>>({
    single_choice: { enabled: true, count: 5 },
    word_form: { enabled: false, count: 5 },
    sentence_rewriting: { enabled: false, count: 5 },
  } as Record<QuestionType, RowState>)
  const [serverError, setServerError] = useState<string | null>(null)
  const [upgradeReason, setUpgradeReason] = useState<string | null>(null)

  const { generate, guard, isPending, locked, freeRemaining } = useGeneratePaper(setServerError)
  const quotaNotice = generateQuotaNotice(locked, freeRemaining)

  // 互斥:chip 与自定义输入二选一
  const pickScene = (s: string) => {
    setScene((prev) => (prev === s ? null : s))
    setCustom('')
  }
  const typeCustom = (v: string) => {
    setCustom(v)
    if (v.trim() !== '') setScene(null)
  }

  const topic = custom.trim() !== '' ? custom.trim() : (scene ?? '')
  const entries: ComposeEntry[] = THEME_TYPES.filter((t) => rows[t].enabled).map((t) => ({
    type: t,
    count: rows[t].count,
  }))
  const input: ComposeInput = { entries, intensity: 'fresh', topic }

  const ready = topic !== '' && entries.length > 0
  const hasError = validateCompose(input).some((i) => i.level === 'error')

  const submit = () => {
    setServerError(null)
    const reason = guard('fresh')
    if (reason) {
      setUpgradeReason(reason)
      return
    }
    generate({ user_query: composeQuery(input), mode: 'fresh' })
  }

  return (
    <div className="max-w-[44rem]">
      <PageHeader
        title="主题出卷"
        intro="挑一个话题，配上题型——AI 围绕这个场景全新命题。"
      />

      <div className="flex flex-col gap-10">
        {/* 主题区 */}
        <section className="flex flex-col gap-3 border-t border-hairline pt-6">
          <span className="font-ui text-[11px] font-bold tracking-[0.14em] text-quiet">
            主题
          </span>
          <div className="flex flex-wrap gap-2">
            {SCENES.map((s) => (
              <button
                key={s}
                type="button"
                aria-pressed={scene === s}
                className={cn(
                  'rounded-sm border px-3 py-1 font-ui text-[12.5px] transition-colors',
                  scene === s
                    ? 'border-accent bg-wash text-accent'
                    : 'border-hairline text-muted-ink hover:border-accent hover:text-accent',
                )}
                onClick={() => pickScene(s)}
              >
                {s}
              </button>
            ))}
          </div>
          <input
            type="text"
            value={custom}
            placeholder="也可以自己写，如“太空探索”"
            className="max-w-[24rem] rounded-[3px] border border-ink-20 bg-transparent px-3 py-2 text-[14px] text-ink outline-none transition-colors placeholder:text-quiet focus:border-accent"
            onChange={(e) => typeCustom(e.target.value)}
          />
        </section>

        {/* 题型配比区 */}
        <section className="flex flex-col gap-3 border-t border-hairline pt-6">
          <span className="font-ui text-[11px] font-bold tracking-[0.14em] text-quiet">
            题型与数量
          </span>
          <p className="text-[13px] leading-relaxed text-quiet">
            主题出题目前支持语法三类；听力与阅读按篇章固定出题，暂不支持主题。
          </p>
          <div className="divide-y divide-ink-10 border-y border-hairline">
            {THEME_TYPES.map((t) => {
              const row = rows[t]
              return (
                <div key={t} className="flex flex-wrap items-center gap-x-4 gap-y-2 px-2 py-3.5">
                  <CheckSquare
                    checked={row.enabled}
                    label={`${TYPE_LABELS[t]}参与出题`}
                    onChange={() =>
                      setRows((prev) => ({
                        ...prev,
                        [t]: { ...prev[t], enabled: !prev[t].enabled },
                      }))
                    }
                  />
                  <span
                    className={cn(
                      'w-20 text-[14px] transition-colors',
                      row.enabled ? 'text-ink' : 'text-quiet',
                    )}
                  >
                    {TYPE_LABELS[t]}
                  </span>
                  <div className="flex items-center gap-2">
                    {COUNT_TIERS.map((n) => (
                      <button
                        key={n}
                        type="button"
                        disabled={!row.enabled}
                        aria-pressed={row.enabled && row.count === n}
                        className={cn(
                          'rounded-sm border px-2.5 py-1 font-ui text-[12.5px] leading-none tabular-nums transition-colors disabled:pointer-events-none disabled:opacity-40',
                          row.enabled && row.count === n
                            ? 'border-accent bg-wash text-ink'
                            : 'border-hairline text-muted-ink hover:bg-tint hover:text-ink',
                        )}
                        onClick={() =>
                          setRows((prev) => ({ ...prev, [t]: { ...prev[t], count: n } }))
                        }
                      >
                        {n} 道
                      </button>
                    ))}
                  </div>
                </div>
              )
            })}
          </div>
        </section>

        {/* 预览与提交 */}
        <section className="flex flex-col gap-4">
          {ready ? (
            <QueryPreview input={input} />
          ) : (
            <div className="flex flex-col gap-2 border-t border-hairline pt-4">
              <span className="font-ui text-[11px] font-bold tracking-[0.14em] text-quiet">
                将向 AI 发送
              </span>
              <p className="text-[13px] text-quiet">
                {topic === '' ? '先挑一个主题（或自己写一个）' : '至少勾选一种题型'}
                ，这里会出现将要发送的句子。
              </p>
            </div>
          )}
          <div className="flex flex-col items-start gap-2">
            <button
              type="button"
              disabled={!ready || hasError || isPending}
              className="rounded-sm border border-accent bg-wash px-6 py-2.5 font-ui text-[15px] tracking-[0.05em] text-ink transition-colors hover:text-accent disabled:pointer-events-none disabled:opacity-60"
              onClick={submit}
            >
              {isPending ? '正在组卷…' : '按主题出卷'}
            </button>
            {serverError && <p className="text-[12px] text-accent">{serverError}</p>}
            {quotaNotice && (
              <p className="font-ui text-[12px] tabular-nums text-quiet">{quotaNotice}</p>
            )}
          </div>
          {isPending && <PipelineProgress />}
        </section>

        {/* 页脚双链接 */}
        <div className="flex flex-wrap gap-x-8 gap-y-2 border-t border-hairline pt-4 font-ui text-[13px]">
          <Link to={PATHS.mock} className="text-muted-ink transition-colors hover:text-accent">
            想练篇章题？去 整卷模拟 →
          </Link>
          <Link
            to={PATHS.practiceCustom}
            className="text-muted-ink transition-colors hover:text-accent"
          >
            想精确配比？去 自选组卷 →
          </Link>
        </div>
      </div>

      <UpgradeDialog reason={upgradeReason} onClose={() => setUpgradeReason(null)} />
    </div>
  )
}
