import { Link } from 'react-router-dom'
import type { MasteryProfile } from '@/types/api'
import { PATHS } from '@/lib/paths'
import { TYPE_LABELS, prettifyKp } from '@/lib/kp'
import { useKnowledgePoints } from '@/hooks/useKnowledgePoints'
import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/EmptyState'
import { cn } from '@/lib/utils'

/**
 * 掌握度分级（Spec F v2.2 三色 band）：< 0.4 薄弱 = 橙红、
 * 0.4–0.7 一般 = 赭黄、≥ 0.7 扎实 = 绿。条与分数同色，一眼扫出节奏。
 */
const WEAK_THRESHOLD = 0.4
const SOLID_THRESHOLD = 0.7

const bandOf = (m: number) => (m < WEAK_THRESHOLD ? 'weak' : m < SOLID_THRESHOLD ? 'mid' : 'solid')
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

export function MasteryReport({
  profile,
  hideActionCta = false,
}: {
  profile: MasteryProfile
  /** admin 端查看他人画像时置 true，隐藏「去错题本重练」CTA */
  hideActionCta?: boolean
}) {
  useKnowledgePoints() // 确保目录到达后重渲染，考点显示为中文名
  if (profile.total_attempts_considered === 0) {
    return (
      <EmptyState
        title="还没有答题记录"
        desc="做几份试卷之后，这里会标出你最需要巩固的考点"
        action={
          <Button asChild>
            <Link to={PATHS.dashboard}>去生成一份</Link>
          </Button>
        }
      />
    )
  }

  const sorted = [...profile.weak_kps].sort((a, b) => a.mastery - b.mastery)
  const weakest = sorted[0]
  const weakCount = sorted.filter((kp) => kp.mastery < WEAK_THRESHOLD).length

  return (
    <div className="flex flex-col gap-8">
      {/* 顶部统计 */}
      <div className="flex flex-wrap items-end gap-x-10 gap-y-4 border-b border-hairline pb-6">
        <Stat label="纳入统计" value={String(profile.total_attempts_considered)} unit="次作答" />
        <Stat label="覆盖考点" value={String(sorted.length)} unit="个" />
        <Stat
          label="建议优先补的薄弱点"
          value={String(weakCount)}
          unit="个"
          accent={weakCount > 0}
        />
        {profile.writing_graded_count > 0 && profile.writing_avg_score != null && (
          <Stat
            label="写作平均分"
            value={String(profile.writing_avg_score)}
            unit={`/ ${profile.writing_full_score} 分 · ${profile.writing_graded_count} 篇`}
          />
        )}
        {profile.dominant_types.length > 0 && (
          <span className="pb-1 text-[13px] text-quiet">
            主要练习：{profile.dominant_types.map((t) => TYPE_LABELS[t] ?? t).join('、')}
          </span>
        )}
      </div>

      {/* 考点行：名称+次数 / 进度条 / 分数 */}
      <div className="flex flex-col">
        {sorted.map((kp) => {
          const band = bandOf(kp.mastery)
          return (
            <div
              key={kp.knowledge_point_id}
              className="grid grid-cols-[minmax(0,1fr)_200px_64px] items-center gap-4 border-b border-hairline py-[14px] max-sm:grid-cols-[minmax(0,1fr)_64px]"
            >
              <div className="flex min-w-0 flex-col gap-0.5">
                <span className="truncate text-[14.5px] text-ink" title={kp.knowledge_point_id}>
                  {prettifyKp(kp.knowledge_point_id)}
                </span>
                <span className="truncate font-mono text-[11px] text-quiet">
                  {kp.knowledge_point_id} · {kp.attempts} 次作答
                </span>
              </div>
              <div className="h-1 overflow-hidden bg-ink-10 max-sm:hidden">
                <div
                  className={cn('h-full', BAND_BAR[band])}
                  style={{ width: `${Math.round(kp.mastery * 100)}%` }}
                />
              </div>
              <span
                className={cn('text-right font-mono text-[13px] font-bold', BAND_TEXT[band])}
                title="稳健掌握度（Wilson 下界）：答题次数越少估计越保守"
              >
                {kp.mastery.toFixed(2)}
              </span>
            </div>
          )
        })}
      </div>

      {/* 底部：薄弱点总结 + 出卷入口（admin 端隐藏 CTA） */}
      {weakest && weakest.mastery < 0.7 && (
        <div className="flex flex-wrap items-center justify-between gap-4">
          <span className="text-[13.5px] text-muted-ink">
            当前最薄弱：<b className="text-ink">{prettifyKp(weakest.knowledge_point_id)}</b>
            （掌握度 {weakest.mastery.toFixed(2)}），建议从它开始补
          </span>
          {!hideActionCta && (
            <Button asChild size="sm">
              <Link to={PATHS.review}>去错题本重练 →</Link>
            </Button>
          )}
        </div>
      )}
    </div>
  )
}

function Stat({
  label,
  value,
  unit,
  accent,
}: {
  label: string
  value: string
  unit?: string
  accent?: boolean
}) {
  return (
    <div className="flex flex-col gap-1 font-ui">
      <span className="kicker">{label}</span>
      <span
        className={cn(
          'text-[32px] font-bold leading-none tabular-nums',
          accent ? 'text-accent' : 'text-ink',
        )}
      >
        {value}
        {unit && <span className="ml-1 text-[13px] font-[450] text-quiet">{unit}</span>}
      </span>
    </div>
  )
}
