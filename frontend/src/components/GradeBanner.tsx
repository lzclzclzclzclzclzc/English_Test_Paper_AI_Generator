import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'

interface GradeBannerProps {
  earned: number
  total: number
  correctCount: number
  totalCount: number
  wrongCount: number
  onRetry: () => void
  onRemediate: () => void
}

/**
 * 成绩统计行（handoff 第 6 屏）：总分大字 + 答对 / 错题（赤陶），
 * 右侧「按错题生成巩固卷」（主）+「再做一遍」/「查看掌握度」（次）。
 */
export function GradeBanner({
  earned,
  total,
  correctCount,
  totalCount,
  wrongCount,
  onRetry,
  onRemediate,
}: GradeBannerProps) {
  return (
    <div className="kk-rise flex flex-wrap items-end justify-between gap-x-8 gap-y-4 border-b border-hairline pb-6">
      <div className="flex items-end gap-8">
        <div className="flex flex-col gap-1">
          <span className="text-[11px] tracking-[0.1em] text-quiet">总分</span>
          <span className="text-[44px] leading-none text-ink">
            {earned}
            <span className="text-[18px] text-quiet"> / {total}</span>
          </span>
        </div>
        <div className="flex flex-col gap-1 pb-1">
          <span className="text-[11px] tracking-[0.1em] text-quiet">答对</span>
          <span className="text-[24px] leading-none text-ink">
            {correctCount}
            <span className="text-[14px] text-quiet"> / {totalCount}</span>
          </span>
        </div>
        <div className="flex flex-col gap-1 pb-1">
          <span className="text-[11px] tracking-[0.1em] text-quiet">错题</span>
          <span className="text-[24px] leading-none text-accent">{wrongCount}</span>
        </div>
      </div>
      <div className="flex items-center gap-2.5">
        <Button variant="outline" size="sm" onClick={onRetry}>
          再做一遍
        </Button>
        <Button variant="outline" size="sm" asChild>
          <Link to="/mastery">查看掌握度</Link>
        </Button>
        {wrongCount > 0 ? (
          <Button size="sm" onClick={onRemediate}>
            按错题生成巩固卷（{wrongCount} 题）
          </Button>
        ) : (
          <Button size="sm" asChild>
            <Link to="/">出一份新卷</Link>
          </Button>
        )}
      </div>
    </div>
  )
}
