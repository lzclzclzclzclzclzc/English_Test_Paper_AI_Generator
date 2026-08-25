import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getMastery } from '@/api/mastery'
import { useGeneratePaper } from '@/hooks/useGeneratePaper'
import { MasteryReport } from '@/components/MasteryReport'
import { PageHeader } from '@/components/PageHeader'
import { PipelineProgress } from '@/components/PipelineProgress'
import { CreditHint } from '@/components/CreditHint'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { Segmented } from '@/components/ui/segmented'

const WINDOWS = [
  { value: 'all', label: '全部记录', days: undefined },
  { value: '90', label: '近 90 天', days: 90 },
  { value: '30', label: '近 30 天', days: 30 },
  { value: '7', label: '近 7 天', days: 7 },
] as const

/** 「按薄弱考点复习」的统计范围（review_window_days）——独立于顶部的报告窗口 */
const REVIEW_WINDOWS = [7, 30, 90] as const

/**
 * 掌握度（handoff 第 7 屏）：GET /api/users/me/mastery，橙红不透明度分级。
 * 学情报告已独立成 /report 页(2026-08-09 侧栏拆分)——这里只留链接式入口,
 * 学情报告免费（纯统计）。
 */
export function MasteryPage() {
  const [windowKey, setWindowKey] = useState<string>('all')
  const [reviewWindowDays, setReviewWindowDays] = useState<number>(30)
  const [serverError, setServerError] = useState<string | null>(null)
  const { generate, isPending } = useGeneratePaper(setServerError, 'mastery_review')
  const windowMeta = WINDOWS.find((w) => w.value === windowKey)
  const windowDays = windowMeta?.days

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['mastery', 'me', windowKey],
    queryFn: () => getMastery(windowDays),
  })

  const submitReview = () => {
    setServerError(null)
    // 复习卷题数由 AI 按薄弱点决定，价格按全新出题价在服务端结算；余额不足由 402 弹充值
    // 文案保持朴素：带"最近 N 天"等场景语义会触发向量检索（需本机 embedding 模型）；
    // 统计窗口走 review_window_days 参数即可
    generate({
      user_query: '出一份综合复习卷',
      mode: 'review',
      review_window_days: reviewWindowDays,
    })
  }

  const noAttempts = data?.total_attempts_considered === 0

  return (
    <div className="max-w-[56rem]">
      <PageHeader
        title="掌握度"
        intro={
          <>
            根据你的答题记录计算（Wilson 下界）：分数越低的考点
            <mark>越值得优先练</mark>，薄弱点用橙红标出。
          </>
        }
      >
        {/* 统计窗口分段（选中 = 墨色实心） */}
        <Segmented
          aria-label="统计窗口"
          value={windowKey}
          onChange={setWindowKey}
          options={WINDOWS}
        />
      </PageHeader>

      {isLoading ? (
        <div className="flex flex-col gap-3">
          <Skeleton className="h-6 w-1/2" />
          <Skeleton className="h-48 w-full" />
        </div>
      ) : isError || !data ? (
        <div className="flex flex-col items-start gap-3 border-t border-hairline pt-8">
          <p className="text-[13.5px] text-muted-ink">掌握度数据加载失败</p>
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            重试
          </Button>
        </div>
      ) : (
        <MasteryReport profile={data} />
      )}

      {/* 按薄弱考点复习（mode review）——统计范围独立于顶部的报告窗口 */}
      {data && !isLoading && !isError && (
        <section className="mt-10 flex flex-col items-start gap-4 border-t border-hairline pt-8">
          <div className="flex items-center gap-2">
            <span className="kicker">
              按薄弱考点复习
            </span>
            <CreditHint action="generate_fresh" units={10} prefix="10 题约" />
          </div>

          <p className="max-w-[42rem] text-[15px] leading-[1.9] text-muted-ink">
            AI 根据你最近的答题记录找出薄弱考点，出一份查漏补缺的复习卷。
          </p>

          {noAttempts ? (
            <p className="text-[13px] text-quiet">先做几份卷，这里才有的放矢</p>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              <span className="mr-1 font-ui text-[12px] text-quiet">统计范围</span>
              <Segmented
                aria-label="统计范围"
                size="sm"
                value={reviewWindowDays}
                onChange={setReviewWindowDays}
                options={REVIEW_WINDOWS.map((d) => ({ value: d, label: `近 ${d} 天` }))}
              />
            </div>
          )}

          <div className="flex flex-col gap-2">
            <Button
              size="lg"
              type="button"
              disabled={isPending || noAttempts}
              onClick={submitReview}
            >
              {isPending ? '正在组卷…' : '出一份复习卷'}
            </Button>
            {serverError && <p className="text-[12px] text-accent">{serverError}</p>}
          </div>

          {isPending && (
            <div className="w-full self-stretch">
              <PipelineProgress />
            </div>
          )}
        </section>
      )}
    </div>
  )
}
