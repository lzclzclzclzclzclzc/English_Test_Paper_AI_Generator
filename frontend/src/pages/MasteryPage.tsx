import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getMastery } from '@/api/mastery'
import { MasteryReport } from '@/components/MasteryReport'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'

const WINDOWS = [
  { value: 'all', label: '全部记录', days: undefined },
  { value: '90', label: '最近 90 天', days: 90 },
  { value: '30', label: '最近 30 天', days: 30 },
  { value: '7', label: '最近 7 天', days: 7 },
] as const

/** 图例（Spec F § 5 掌握度页：固定在页头右侧）。 */
function Legend() {
  return (
    <div className="flex items-center gap-3 text-xs text-muted-foreground">
      <span className="flex items-center gap-1">
        <i className="size-2 rounded-full bg-ink" /> ≥70%
      </span>
      <span className="flex items-center gap-1">
        <i className="size-2 rounded-full bg-mid-score" /> 40-70%
      </span>
      <span className="flex items-center gap-1">
        <i className="size-2 rounded-full bg-wrong" /> &lt;40%
      </span>
    </div>
  )
}

export function MasteryPage() {
  const [windowKey, setWindowKey] = useState<string>('all')
  const windowDays = WINDOWS.find((w) => w.value === windowKey)?.days

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['mastery', 'me', windowKey],
    queryFn: () => getMastery(windowDays),
  })

  return (
    <div className="mx-auto flex max-w-[760px] flex-col gap-6 px-6 pt-12">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h1 className="font-serif text-2xl font-bold text-foreground">掌握度报告</h1>
          <p className="text-[13.5px] text-text-mid">
            根据你的答题记录计算：分数越低的考点，越值得优先练
          </p>
        </div>
        <div className="flex items-center gap-4">
          <Legend />
          <Select value={windowKey} onValueChange={setWindowKey}>
            <SelectTrigger className="w-[130px]" size="sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {WINDOWS.map((w) => (
                <SelectItem key={w.value} value={w.value}>
                  {w.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {isLoading ? (
        <div className="flex flex-col gap-3">
          <Skeleton className="h-6 w-1/2" />
          <Skeleton className="h-48 w-full" />
        </div>
      ) : isError || !data ? (
        <div className="flex flex-col items-center gap-3 py-16">
          <p className="text-[13.5px] text-muted-foreground">掌握度数据加载失败</p>
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            重试
          </Button>
        </div>
      ) : (
        <MasteryReport profile={data} />
      )}
    </div>
  )
}
