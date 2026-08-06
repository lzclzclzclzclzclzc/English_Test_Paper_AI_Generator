import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getMastery } from '@/api/mastery'
import { useMembership } from '@/hooks/useMembership'
import { MasteryReport } from '@/components/MasteryReport'
import { StudyReport } from '@/components/StudyReport'
import { PageHeader } from '@/components/PageHeader'
import { MemberPill, UpgradeDialog } from '@/components/UpgradeDialog'
import { cn } from '@/lib/utils'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'

const WINDOWS = [
  { value: 'all', label: '全部记录', days: undefined },
  { value: '90', label: '近 90 天', days: 90 },
  { value: '30', label: '近 30 天', days: 30 },
  { value: '7', label: '近 7 天', days: 7 },
] as const

/** 掌握度（handoff 第 7 屏）：GET /api/users/me/mastery，赤陶不透明度分级。 */
export function MasteryPage() {
  const [windowKey, setWindowKey] = useState<string>('all')
  const [reportOpen, setReportOpen] = useState(false)
  const [upgradeReason, setUpgradeReason] = useState<string | null>(null)
  const { locked } = useMembership()
  const windowMeta = WINDOWS.find((w) => w.value === windowKey)
  const windowDays = windowMeta?.days

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['mastery', 'me', windowKey],
    queryFn: () => getMastery(windowDays),
  })

  const handleReportClick = () => {
    if (locked) {
      setUpgradeReason('学情报告是会员功能：一页纸汇总练习量与薄弱考点，可打印给家长。')
      return
    }
    setReportOpen((v) => !v)
  }

  return (
    <div className="max-w-[56rem]">
      {/* 打印学情报告时隐藏页面其他部分,只留报告本体 */}
      <div className="print:hidden">
        <PageHeader
          title="掌握度"
          intro={
            <>
              根据你的答题记录计算（Wilson 下界）：分数越低的考点
              <mark>越值得优先练</mark>，薄弱点用赤陶标出。
            </>
          }
        >
          {/* 统计窗口：分段按钮（选中 = 赤陶边 + wash 底） */}
          <div className="flex flex-wrap items-center gap-2">
            {WINDOWS.map((w) => (
              <button
                key={w.value}
                type="button"
                aria-pressed={windowKey === w.value}
                onClick={() => setWindowKey(w.value)}
                className={cn(
                  'rounded-sm border px-3 py-1.5 text-[13px] transition-colors',
                  windowKey === w.value
                    ? 'border-accent bg-wash text-ink'
                    : 'border-hairline text-muted-ink hover:bg-tint hover:text-ink',
                )}
              >
                {w.label}
              </button>
            ))}
            <Button variant="outline" size="sm" onClick={handleReportClick}>
              {reportOpen ? '收起学情报告' : '生成学情报告'}
              {locked && <MemberPill className="ml-1.5" />}
            </Button>
          </div>
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
      </div>

      {reportOpen && data && (
        <StudyReport
          profile={data}
          windowLabel={windowMeta?.label ?? '全部记录'}
          onClose={() => setReportOpen(false)}
        />
      )}

      <UpgradeDialog reason={upgradeReason} onClose={() => setUpgradeReason(null)} />
    </div>
  )
}
