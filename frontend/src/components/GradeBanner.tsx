import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { PATHS } from '@/lib/paths'

interface GradeBannerProps {
  correctCount: number
  totalCount: number
  wrongCount: number
  onRetry: () => void
  onRemediate: () => void
  remediating?: boolean
  /** 组好的错题巩固卷 id，有值时按钮变「跳转试卷」 */
  remediatedPaperId?: string | null
  onOpenRemediation?: () => void
}

/**
 * 成绩统计行（handoff 第 6 屏）：答对大字 + 错题（赤陶），右侧
 * 「按错题生成巩固卷」（主，组好后变「跳转试卷」）+「再做一遍」/「查看掌握度」（次）。
 */
export function GradeBanner({
  correctCount,
  totalCount,
  wrongCount,
  onRetry,
  onRemediate,
  remediating = false,
  remediatedPaperId = null,
  onOpenRemediation,
}: GradeBannerProps) {
  const renderRemediateButton = () => {
    if (remediatedPaperId) {
      return (
        <Button size="sm" onClick={onOpenRemediation}>
          跳转巩固卷 →
        </Button>
      )
    }
    return (
      <Button size="sm" onClick={onRemediate} disabled={remediating}>
        {remediating ? '正在组卷…' : `按错题生成巩固卷（${wrongCount} 题）`}
      </Button>
    )
  }

  // 正确率分band（v2.2）：≥80% 绿 / ≥60% 赭黄 / 以下赤陶
  const rate = totalCount === 0 ? 0 : correctCount / totalCount
  const rateColor = rate >= 0.8 ? 'text-success' : rate >= 0.6 ? 'text-grammar' : 'text-accent'

  return (
    <div className="kk-rise flex flex-wrap items-end justify-between gap-x-8 gap-y-4 border-b border-hairline pb-6">
      <div className="flex items-end gap-8 font-ui">
        <div className="flex flex-col gap-1">
          <span className="text-[11px] font-[550] tracking-[0.1em] text-quiet">答对</span>
          <span className="text-[54px] font-[750] leading-none tabular-nums text-success">
            {correctCount}
            <span className="text-[18px] font-[450] text-quiet"> / {totalCount}</span>
          </span>
        </div>
        <div className="flex flex-col gap-1 pb-1">
          <span className="text-[11px] font-[550] tracking-[0.1em] text-quiet">错题</span>
          <span className="text-[28px] font-[650] leading-none tabular-nums text-accent">
            {wrongCount}
          </span>
        </div>
        <div className="flex flex-col gap-1 pb-1">
          <span className="text-[11px] font-[550] tracking-[0.1em] text-quiet">正确率</span>
          <span className={`text-[28px] font-[650] leading-none tabular-nums ${rateColor}`}>
            {Math.round(rate * 100)}
            <span className="text-[14px] font-[450]">%</span>
          </span>
        </div>
        {remediatedPaperId && (
          <span className="pb-1 text-[13px] text-quiet">已生成错题巩固卷，点右侧进入</span>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-2.5">
        <Button variant="outline" size="sm" onClick={onRetry}>
          再做一遍
        </Button>
        <Button variant="outline" size="sm" asChild>
          <Link to="/mastery">查看掌握度</Link>
        </Button>
        {wrongCount > 0 ? (
          renderRemediateButton()
        ) : (
          <Button size="sm" asChild>
            <Link to={PATHS.dashboard}>出一份新卷</Link>
          </Button>
        )}
      </div>
    </div>
  )
}
