import { Link } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { useKnowledgePoints } from '@/hooks/useKnowledgePoints'
import type { ComposeInput } from '@/lib/composeQuery'
import { prettifyKp } from '@/lib/kp'
import { PATHS } from '@/lib/paths'
import type { MasteryProfile } from '@/types/api'

/** 三色 band（手法同 MasteryReport）：< 0.4 赤陶 / 0.4–0.7 赭黄 / ≥ 0.7 绿 */
const bandOf = (m: number) => (m < 0.4 ? 'weak' : m < 0.7 ? 'mid' : 'solid')
const BAND_BAR: Record<string, string> = {
  weak: 'bg-accent',
  mid: 'bg-grammar',
  solid: 'bg-success',
}
const BAND_TEXT: Record<string, string> = {
  weak: 'text-accent',
  mid: 'text-grammar',
  solid: 'text-success',
}

interface WeakSpotsProps {
  mastery: MasteryProfile
  isPending: boolean
  /** 专练一个考点（8 道对应题型）；guard 拦截时由父级弹升级框 */
  onDrill: (input: ComposeInput) => void
}

/**
 * 弱点速览：近 30 天最弱 3 个考点，行式三色 band + 「专练 →」直出 8 道；
 * 无答题记录时空态引导去练习中心。
 */
export function WeakSpots({ mastery, isPending, onDrill }: WeakSpotsProps) {
  const kpQuery = useKnowledgePoints()
  const weakest = [...mastery.weak_kps].sort((a, b) => a.mastery - b.mastery).slice(0, 3)
  const empty = mastery.total_attempts_considered === 0

  return (
    <section className="flex flex-col gap-3 border-t border-hairline pt-6">
      <div className="flex items-baseline justify-between gap-4">
        <span className="font-ui text-[11px] font-bold tracking-[0.14em] text-quiet">
          弱点速览 · 近 30 天
        </span>
        {!empty && (
          <Link
            to={PATHS.mastery}
            className="text-[12.5px] text-quiet transition-colors hover:text-accent"
          >
            完整报告 →
          </Link>
        )}
      </div>

      {empty ? (
        <div className="flex flex-col items-start gap-2 py-1">
          <p className="text-[14px] text-ink">先做一份卷，这里会标出你的薄弱考点</p>
          <Link
            to={PATHS.practice}
            className="text-[13px] text-accent underline underline-offset-2"
          >
            去练习中心 →
          </Link>
        </div>
      ) : weakest.length === 0 ? (
        <p className="text-[13px] text-quiet">近 30 天没有需要补的考点——保持节奏</p>
      ) : (
        <div className="divide-y divide-ink-10">
          {weakest.map((kp) => {
            const band = bandOf(kp.mastery)
            const cat = kpQuery.data?.find((c) => c.id === kp.knowledge_point_id)
            return (
              <div
                key={kp.knowledge_point_id}
                className="grid grid-cols-[minmax(0,1fr)_140px_48px_auto] items-center gap-4 px-2 py-3 max-sm:grid-cols-[minmax(0,1fr)_48px_auto]"
              >
                <span
                  className="truncate text-[14px] text-ink"
                  title={kp.knowledge_point_id}
                >
                  {prettifyKp(kp.knowledge_point_id)}
                </span>
                <div className="h-[6px] overflow-hidden rounded-full bg-ink-10 max-sm:hidden">
                  <div
                    className={cn('h-full rounded-full', BAND_BAR[band])}
                    style={{ width: `${Math.round(kp.mastery * 100)}%` }}
                  />
                </div>
                <span
                  className={cn(
                    'text-right font-ui text-[13px] font-[650] tabular-nums',
                    BAND_TEXT[band],
                  )}
                >
                  {Math.round(kp.mastery * 100)}%
                </span>
                {cat ? (
                  <button
                    type="button"
                    disabled={isPending}
                    className="text-[13px] text-quiet transition-colors hover:text-accent disabled:pointer-events-none disabled:opacity-60"
                    onClick={() =>
                      onDrill({ entries: [{ type: cat.level1, count: 8, kps: [cat.level2] }] })
                    }
                  >
                    专练 →
                  </button>
                ) : (
                  <span aria-hidden className="text-[13px] text-transparent">
                    专练 →
                  </span>
                )}
              </div>
            )
          })}
        </div>
      )}
    </section>
  )
}
