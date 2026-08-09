import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { getMastery } from '@/api/mastery'
import { useMembership } from '@/hooks/useMembership'
import { PageHeader } from '@/components/PageHeader'
import { StudyReport } from '@/components/StudyReport'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { PATHS } from '@/lib/paths'

/**
 * 学情报告页(自掌握度页独立,2026-08-09 侧栏拆分):
 * 会员看完整报告(StudyReport,打印时只留报告本体);非会员看居中提示
 * 与开通入口——掌握度页的入口对非会员照样可点,拦截在这里呈现。
 * 统计窗口固定近 30 天(与工作台掌握度缓存同键)。
 */
export function ReportPage() {
  const { locked } = useMembership()

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['mastery', 'me', '30'],
    queryFn: () => getMastery(30),
    enabled: !locked,
  })

  if (locked) {
    return (
      <div className="max-w-[56rem]">
        {/* 非会员:居中提示 + 唯一下一步 */}
        <div className="mx-auto mt-20 flex max-w-[26rem] flex-col items-center gap-4 border-t border-accent pt-8 text-center">
          <span className="font-ui text-[11px] font-bold tracking-[0.14em] text-quiet">
            学情报告 · 会员功能
          </span>
          <p className="text-[15px] leading-[1.9] text-muted-ink">
            一页纸汇总近 30 天练习量、薄弱考点与下一步建议，可打印给家长。
          </p>
          <Link
            to={PATHS.membership}
            className="rounded-sm border border-accent bg-wash px-6 py-2.5 font-ui text-[15px] tracking-[0.05em] text-ink transition-colors hover:text-accent"
          >
            去开通会员
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-[56rem]">
      {/* 打印时隐藏页头,只留报告本体 */}
      <div className="print:hidden">
        <PageHeader
          title="学情报告"
          intro="一页纸汇总练习量、薄弱考点与下一步建议——可以直接打印给家长。"
        />
      </div>

      {isLoading ? (
        <div className="flex flex-col gap-3 print:hidden">
          <Skeleton className="h-6 w-1/2" />
          <Skeleton className="h-48 w-full" />
        </div>
      ) : isError || !data ? (
        <div className="flex flex-col items-start gap-3 border-t border-hairline pt-8 print:hidden">
          <p className="text-[13.5px] text-muted-ink">学情数据加载失败</p>
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            重试
          </Button>
        </div>
      ) : (
        <StudyReport profile={data} windowLabel="近 30 天" />
      )}
    </div>
  )
}
