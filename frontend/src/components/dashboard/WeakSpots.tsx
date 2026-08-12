import { cn } from '@/lib/utils'
import { useKnowledgePoints } from '@/hooks/useKnowledgePoints'
import type { ComposeInput } from '@/lib/composeQuery'
import { prettifyKp } from '@/lib/kp'
import type { MasteryProfile } from '@/types/api'

/** 三色 band（手法同 MasteryReport）：< 0.4 赤陶 / 0.4–0.7 赭黄 / ≥ 0.7 绿 */
const bandOf = (m: number) => (m < 0.4 ? 'weak' : m < 0.7 ? 'mid' : 'solid')
const BAND_BAR: Record<string, string> = {
  weak: 'bg-accent',
  mid: 'bg-grammar',
  solid: 'bg-success',
}

interface WeakSpotsProps {
  /** undefined = 掌握度还没到（加载中/失败），只显示 kicker 不占位内容 */
  mastery: MasteryProfile | undefined
  isPending: boolean
  /** 专练一个考点（8 道对应题型）；guard 拦截时由父级弹升级框 */
  onDrill: (input: ComposeInput) => void
}

/**
 * 弱点速览（工作台右栏窄版）：近 30 天最弱 4 个考点，每行考点名 +
 * 三色 band 条 + 「专练 →」直出 8 道；无答题记录时一句空态引导。
 */
export function WeakSpots({ mastery, isPending, onDrill }: WeakSpotsProps) {
  const kpQuery = useKnowledgePoints()
  const weakest = [...(mastery?.weak_kps ?? [])].sort((a, b) => a.mastery - b.mastery).slice(0, 4)
  const empty = mastery !== undefined && mastery.total_attempts_considered === 0

  return (
    <section className="flex flex-col gap-3 pb-5">
      <span className="font-ui text-[11px] font-bold tracking-[0.14em] text-quiet">
        弱点速览 · 近 30 天
      </span>

      {empty ? (
        <p className="px-2 text-[12.5px] leading-[1.8] text-quiet">
          先做一份卷，这里会标出你的薄弱考点
        </p>
      ) : weakest.length === 0 ? (
        mastery && (
          <p className="px-2 text-[12.5px] leading-[1.8] text-quiet">
            近 30 天没有需要补的考点——保持节奏
          </p>
        )
      ) : (
        <div className="flex flex-col gap-1">
          {weakest.map((kp) => {
            const band = bandOf(kp.mastery)
            const cat = kpQuery.data?.find((c) => c.id === kp.knowledge_point_id)
            return (
              <div
                key={kp.knowledge_point_id}
                className="flex flex-col gap-1.5 px-2 py-2"
              >
                <div className="flex items-baseline justify-between gap-3">
                  <span
                    className="min-w-0 truncate text-[13.5px] text-ink"
                    title={kp.knowledge_point_id}
                  >
                    {prettifyKp(kp.knowledge_point_id)}
                  </span>
                  {cat && (
                    <button
                      type="button"
                      disabled={isPending}
                      className="shrink-0 font-ui text-[12.5px] text-quiet transition-colors hover:text-accent disabled:pointer-events-none disabled:opacity-60"
                      onClick={() =>
                        onDrill({ entries: [{ type: cat.level1, count: 8, kps: [cat.level2] }] })
                      }
                    >
                      专练 →
                    </button>
                  )}
                </div>
                <div className="h-[5px] overflow-hidden rounded-full bg-ink-10">
                  <div
                    className={cn('h-full rounded-full', BAND_BAR[band])}
                    style={{ width: `${Math.round(kp.mastery * 100)}%` }}
                  />
                </div>
              </div>
            )
          })}
        </div>
      )}
    </section>
  )
}
