import { Link } from 'react-router-dom'
import type { MasteryProfile } from '@/types/api'
import { TYPE_LABELS, prettifyKp } from '@/lib/kp'
import { useKnowledgePoints } from '@/hooks/useKnowledgePoints'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

/**
 * 掌握度颜色阈值（Spec F § 2.2）：≥0.7 用主色藏青（绿只表"答对"），
 * 0.4-0.7 用 --mid-score，<0.4 用 --wrong。
 */
function masteryColor(m: number): { bar: string; text: string } {
  if (m >= 0.7) return { bar: 'bg-ink', text: 'text-ink' }
  if (m >= 0.4) return { bar: 'bg-mid-score', text: 'text-mid-score' }
  return { bar: 'bg-wrong', text: 'text-wrong' }
}

export function MasteryReport({ profile }: { profile: MasteryProfile }) {
  useKnowledgePoints()  // 确保目录到达后重渲染，考点显示为中文名
  if (profile.total_attempts_considered === 0) {
    return (
      <div className="flex flex-col items-center gap-4 rounded-md border border-line bg-sheet px-6 py-16 text-center">
        <p className="font-serif text-base font-bold text-foreground">还没有答题记录</p>
        <p className="text-[13px] text-text-mid">
          做几份试卷之后，这里会标出你最需要巩固的考点
        </p>
        <Button asChild>
          <Link to="/">去生成一份</Link>
        </Button>
      </div>
    )
  }

  const sorted = [...profile.weak_kps].sort((a, b) => a.mastery - b.mastery)
  const weakest = sorted[0]

  return (
    <div className="flex flex-col gap-6">
      {/* 概览 */}
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-[13.5px] text-text-mid">
        <span>
          纳入统计 <b className="text-foreground">{profile.total_attempts_considered}</b> 次作答
        </span>
        {profile.dominant_types.length > 0 && (
          <span className="flex items-center gap-1.5">
            主要练习：
            {profile.dominant_types.map((t) => (
              <span
                key={t}
                className="rounded-full border border-line-strong bg-sheet px-2.5 py-0.5 text-xs"
              >
                {TYPE_LABELS[t] ?? t}
              </span>
            ))}
          </span>
        )}
      </div>

      {/* 考点条形列表 */}
      <div className="flex flex-col divide-y divide-line-soft rounded-md border border-line bg-sheet px-5">
        {sorted.map((kp) => {
          const color = masteryColor(kp.mastery)
          return (
            <div
              key={kp.knowledge_point_id}
              className="grid grid-cols-[170px_1fr_150px] items-center gap-4 py-3 max-sm:grid-cols-1 max-sm:gap-1.5"
            >
              <span className="truncate text-[13.5px] text-foreground" title={kp.knowledge_point_id}>
                {prettifyKp(kp.knowledge_point_id)}
              </span>
              <div className="h-2 overflow-hidden rounded-full bg-line-soft">
                <div
                  className={cn('h-full rounded-full', color.bar)}
                  style={{ width: `${Math.round(kp.mastery * 100)}%` }}
                />
              </div>
              <span className="text-right text-[13px]">
                <b
                  className={cn('font-bold', color.text)}
                  title="稳健掌握度（Wilson 下界）：答题次数越少估计越保守"
                >
                  {Math.round(kp.mastery * 100)}%
                </b>
                <span className="ml-1.5 text-muted-foreground">
                  {kp.attempts} 次
                </span>
              </span>
            </div>
          )
        })}
      </div>

      {/* 最薄弱提示条：指向错题复习页（综合复习就是按画像出卷） */}
      {weakest && weakest.mastery < 0.7 && (
        <div className="flex items-center justify-between rounded-md border border-[#d8e0ea] bg-ink-wash px-5 py-3.5">
          <span className="text-[13.5px] text-ink">
            建议优先巩固：<b>{prettifyKp(weakest.knowledge_point_id)}</b>（当前{' '}
            {Math.round(weakest.mastery * 100)}%）
          </span>
          <Button asChild size="sm">
            <Link to="/review">针对性练一份</Link>
          </Button>
        </div>
      )}
    </div>
  )
}
