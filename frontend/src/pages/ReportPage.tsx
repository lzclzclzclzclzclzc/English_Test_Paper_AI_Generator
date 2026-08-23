import { useQuery } from '@tanstack/react-query'
import { getMastery } from '@/api/mastery'
import { PageHeader } from '@/components/PageHeader'
import { StudyReport } from '@/components/StudyReport'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'

/**
 * 学情报告页(自掌握度页独立,2026-08-09 侧栏拆分):
 * 完整报告(StudyReport,打印时只留报告本体),纯统计、免费。
 * 统计窗口固定近 30 天(与工作台掌握度缓存同键)。
 */
export function ReportPage() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['mastery', 'me', '30'],
    queryFn: () => getMastery(30),
  })

  return (
    <div className="max-w-[56rem]">
      {/* 打印时隐藏页头,只留报告本体 */}
      <div className="print:hidden">
        <PageHeader
          title="学情报告"
          intro="一页纸汇总练习量、薄弱考点与下一步建议——可以直接打印给家长。"
        >
          {data && (
            <Button variant="outline" onClick={() => window.print()}>
              打印这份报告
            </Button>
          )}
        </PageHeader>
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
        <StudyReport profile={data} windowLabel="近 30 天" titleOnlyInPrint />
      )}
    </div>
  )
}
