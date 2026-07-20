import { useState } from 'react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { MemberPill } from '@/components/UpgradeDialog'

const WINDOWS = [7, 30, 90] as const

interface ReviewGeneratePanelProps {
  /** true = 已确认非会员（两个出卷入口都是会员功能） */
  locked: boolean
  isPending: boolean
  wrongTotal: number
  selectedCount: number
  onRemediate: (extraQuery: string) => void
  onReview: (windowDays: number) => void
  /** ai.parser_failed / ai.no_candidate 的面板内提示 */
  serverError: string | null
}

/** 错题复习页的两个出卷入口：错题巩固（基于错题本勾选）+ 综合复习（服务端画像）。 */
export function ReviewGeneratePanel({
  locked,
  isPending,
  wrongTotal,
  selectedCount,
  onRemediate,
  onReview,
  serverError,
}: ReviewGeneratePanelProps) {
  const [extraQuery, setExtraQuery] = useState('')
  const [windowDays, setWindowDays] = useState<number>(30)
  const remediationDisabled = wrongTotal === 0 || selectedCount === 0

  return (
    <div className="flex flex-col gap-2">
      <div className="grid grid-cols-2 gap-4 max-sm:grid-cols-1">
        {/* 错题巩固 */}
        <div className="flex flex-col gap-3 rounded-md border border-line bg-sheet p-5">
          <div className="flex items-center gap-1.5">
            <span className="font-serif text-[15px] font-bold text-foreground">错题巩固</span>
            {locked && <MemberPill />}
          </div>
          <p className="text-[13px] leading-relaxed text-text-mid">
            {wrongTotal === 0
              ? '交卷后答错的题会自动收进错题本，攒下错题后可在这里定向巩固'
              : `已选 ${selectedCount} / 共 ${wrongTotal} 道错题，AI 会围绕它们的考点出一份新卷`}
          </p>
          {/* name/autoComplete/data-1p-ignore：阻止密码管理器把它当登录框弹填充 */}
          <Input
            type="text"
            name="remediation-note"
            autoComplete="off"
            data-1p-ignore
            data-lpignore="true"
            value={extraQuery}
            maxLength={2000}
            placeholder="补充要求（可选），如：多出几道选择题"
            onChange={(e) => setExtraQuery(e.target.value)}
          />
          <Button
            className="mt-auto"
            disabled={remediationDisabled || isPending}
            title={wrongTotal === 0 ? '交卷后答错的题会自动收进错题本' : undefined}
            onClick={() => onRemediate(extraQuery.trim())}
          >
            {isPending ? '正在组卷…' : `错题巩固（${selectedCount} 题）`}
          </Button>
        </div>

        {/* 综合复习 */}
        <div className="flex flex-col gap-3 rounded-md border border-line bg-sheet p-5">
          <div className="flex items-center gap-1.5">
            <span className="font-serif text-[15px] font-bold text-foreground">综合复习</span>
            {locked && <MemberPill />}
          </div>
          <p className="text-[13px] leading-relaxed text-text-mid">
            AI 根据你的答题记录算出薄弱考点，出一份查漏补缺的复习卷
          </p>
          <div className="flex items-baseline gap-x-4 text-[13.5px]">
            <span className="text-xs text-text-mid">统计范围</span>
            {WINDOWS.map((d) => (
              <button
                key={d}
                type="button"
                aria-pressed={windowDays === d}
                onClick={() => setWindowDays(d)}
                className={cn(
                  'border-b-2 pb-1 leading-none transition-colors',
                  windowDays === d
                    ? 'border-ink font-bold text-ink'
                    : 'border-transparent text-text-mid hover:text-foreground',
                )}
              >
                近 {d} 天
              </button>
            ))}
          </div>
          <Button
            className="mt-auto"
            disabled={isPending}
            onClick={() => onReview(windowDays)}
          >
            {isPending ? '正在组卷…' : '出一份复习卷'}
          </Button>
        </div>
      </div>
      {serverError && <p className="text-xs text-wrong">{serverError}</p>}
    </div>
  )
}
