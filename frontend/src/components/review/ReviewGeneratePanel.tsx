import { useState } from 'react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
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

/** 错题本页的两个出卷入口：错题巩固（基于错题本勾选）+ 综合复习（服务端画像）。 */
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
      <div className="grid grid-cols-2 gap-x-12 border-y border-hairline max-sm:grid-cols-1 max-sm:divide-y max-sm:divide-ink-10 sm:divide-x sm:divide-ink-10">
        {/* 错题巩固 */}
        <div className="flex flex-col gap-3 py-6 sm:pr-12">
          <div className="flex items-center gap-2">
            <span className="text-[12px] tracking-[0.1em] text-accent">REMEDIATION</span>
            <span className="text-[17px] text-ink">错题巩固</span>
            {locked && <MemberPill />}
          </div>
          <p className="text-[14px] leading-[1.9] text-muted-ink">
            {wrongTotal === 0
              ? '交卷后答错的题会自动收进错题本，攒下错题后可在这里定向巩固'
              : `已选 ${selectedCount} / 共 ${wrongTotal} 道错题，AI 会围绕它们的考点出一份新卷`}
          </p>
          {/* name/autoComplete/data-1p-ignore：阻止密码管理器把它当登录框弹填充 */}
          <input
            type="text"
            name="remediation-note"
            autoComplete="off"
            data-1p-ignore
            data-lpignore="true"
            value={extraQuery}
            maxLength={2000}
            placeholder="补充要求（可选），如：多出几道选择题"
            onChange={(e) => setExtraQuery(e.target.value)}
            className="w-full rounded-[3px] border border-ink-20 bg-transparent px-3 py-2 text-[14px] text-ink outline-none transition-colors placeholder:text-quiet focus:border-accent"
          />
          <div className="mt-auto flex items-center gap-3">
            <Button
              disabled={remediationDisabled || isPending}
              title={wrongTotal === 0 ? '交卷后答错的题会自动收进错题本' : undefined}
              onClick={() => onRemediate(extraQuery.trim())}
            >
              {isPending ? '正在组卷…' : '用选中错题生成巩固卷'}
            </Button>
            <span className="text-[12px] text-quiet">
              已选 {selectedCount} 道 · mode=remediation
            </span>
          </div>
        </div>

        {/* 综合复习 */}
        <div className="flex flex-col gap-3 py-6 sm:pl-12">
          <div className="flex items-center gap-2">
            <span className="text-[12px] tracking-[0.1em] text-accent">REVIEW</span>
            <span className="text-[17px] text-ink">综合复习</span>
            {locked && <MemberPill />}
          </div>
          <p className="text-[14px] leading-[1.9] text-muted-ink">
            AI 根据你的答题记录算出薄弱考点，出一份查漏补缺的复习卷
          </p>
          <div className="flex items-baseline gap-x-2 text-[13.5px]">
            <span className="mr-2 text-[12px] text-quiet">统计范围</span>
            {WINDOWS.map((d) => (
              <button
                key={d}
                type="button"
                aria-pressed={windowDays === d}
                onClick={() => setWindowDays(d)}
                className={cn(
                  'rounded-sm border px-2.5 py-1 leading-none transition-colors',
                  windowDays === d
                    ? 'border-accent bg-wash text-ink'
                    : 'border-hairline text-muted-ink hover:bg-tint hover:text-ink',
                )}
              >
                近 {d} 天
              </button>
            ))}
          </div>
          <div className="mt-auto">
            <Button disabled={isPending} onClick={() => onReview(windowDays)}>
              {isPending ? '正在组卷…' : '出一份复习卷'}
            </Button>
          </div>
        </div>
      </div>
      {serverError && <p className="text-[12px] text-accent">{serverError}</p>}
    </div>
  )
}
