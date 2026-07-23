import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'

interface GradeBannerProps {
  wrongCount: number
  onRetry: () => void
  onRemediate: () => void
  remediating?: boolean
  /** 组好的错题巩固卷 id，有值时按钮变「跳转试卷」 */
  remediatedPaperId?: string | null
  onOpenRemediation?: () => void
}

/** 成绩条：「再做一遍」/「错题巩固」动作。判分结果由卷面上的 ✓/✗ 与红章承载。 */
export function GradeBanner({
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
          跳转试卷 →
        </Button>
      )
    }
    return (
      <Button size="sm" onClick={onRemediate} disabled={remediating}>
        {remediating ? '正在组卷…' : `错题巩固（${wrongCount} 题）`}
      </Button>
    )
  }

  return (
    <div className="flex items-center justify-between rounded-md border border-[#d8e0ea] bg-ink-wash px-5 py-3.5">
      <span className="text-[13px] text-text-mid">
        {wrongCount === 0
          ? '全部答对，可以挑战新的考点'
          : remediatedPaperId
            ? '已生成错题巩固卷，点右侧进入'
            : '错题已在卷面标出'}
      </span>
      <div className="flex items-center gap-2.5">
        <Button variant="outline" size="sm" onClick={onRetry}>
          再做一遍
        </Button>
        {wrongCount > 0 ? (
          renderRemediateButton()
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
