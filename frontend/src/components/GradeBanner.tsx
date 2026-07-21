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

/** 成绩条：得分摘要 + 「再做一遍」/「错题巩固」动作。分数章由 PaperSheet 的 stamp 承载。 */
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
    <div className="flex items-center justify-between rounded-md border border-[#d8e0ea] bg-ink-wash px-5 py-3.5">
      <div className="flex items-baseline gap-4">
        <span className="text-[15px] font-bold text-ink">
          得分 {earned} / {total}
        </span>
        <span className="text-[13px] text-text-mid">
          {wrongCount === 0
            ? '全部答对，可以挑战新的考点'
            : `答对 ${correctCount} / ${totalCount} 题，错题已标出`}
        </span>
      </div>
      <div className="flex items-center gap-2.5">
        <Button variant="outline" size="sm" onClick={onRetry}>
          再做一遍
        </Button>
        {wrongCount > 0 ? (
          <Button size="sm" onClick={onRemediate}>
            错题巩固（{wrongCount} 题）
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

/** 分数章（Spec F § 4.5）：右上角旋转红章，只出现在成绩视图的卷面上。 */
export function ScoreStamp({ correctCount, totalCount }: { correctCount: number; totalCount: number }) {
  return (
    <div
      aria-hidden
      className="absolute right-8 top-6 flex rotate-[8deg] items-center justify-center border-[3px] border-wrong px-3 py-1 font-serif text-2xl font-black text-wrong opacity-90"
    >
      {correctCount}/{totalCount}
    </div>
  )
}
