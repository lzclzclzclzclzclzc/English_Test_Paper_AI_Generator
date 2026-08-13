import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useInfiniteQuery } from '@tanstack/react-query'
import { listPapers, type PaperFilters } from '@/api/papers'
import type { PaperListItem } from '@/types/api'
import { PATHS } from '@/lib/paths'
import { TYPE_LABELS } from '@/lib/kp'
import { cn } from '@/lib/utils'
import { PageHeader } from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

const PAGE_SIZE = 20

type StatusFilter = 'all' | 'submitted' | 'unsubmitted'

const STATUS_OPTIONS: { value: StatusFilter; label: string }[] = [
  { value: 'all', label: '全部' },
  { value: 'submitted', label: '已交卷' },
  { value: 'unsubmitted', label: '未作答' },
]

/** 历史试卷（handoff 第 8 屏）：无卡片的行式列表，整行可点。满页即认为还有下一页。 */
export function PapersPage() {
  const [status, setStatus] = useState<StatusFilter>('all')
  const [questionType, setQuestionType] = useState('') // '' = 全部题型
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')

  const hasFilters =
    status !== 'all' || questionType !== '' || startDate !== '' || endDate !== ''

  // 服务端筛选：只发已选项，空值退化为不筛。
  const filters: PaperFilters = {
    submitted: status === 'all' ? undefined : status === 'submitted',
    question_type: questionType || undefined,
    start_date: startDate || undefined,
    end_date: endDate || undefined,
  }

  const clearFilters = () => {
    setStatus('all')
    setQuestionType('')
    setStartDate('')
    setEndDate('')
  }

  const query = useInfiniteQuery({
    queryKey: ['papers', 'list', { status, questionType, startDate, endDate }],
    queryFn: ({ pageParam }) => listPapers(PAGE_SIZE, pageParam, filters),
    initialPageParam: 0,
    getNextPageParam: (last, _all, lastOffset) =>
      last.items.length === PAGE_SIZE ? lastOffset + PAGE_SIZE : undefined,
  })

  const papers = query.data?.pages.flatMap((p) => p.items) ?? []

  return (
    <div className="max-w-[56rem]">
      <PageHeader
        title="历史试卷"
        intro="生成过的卷都在这里，未交的随时开卷，交过的回来复盘。重新生成会得到一份新卷，旧试卷保留。"
      />

      <FilterBar
        status={status}
        onStatusChange={setStatus}
        questionType={questionType}
        onQuestionTypeChange={setQuestionType}
        startDate={startDate}
        onStartDateChange={setStartDate}
        endDate={endDate}
        onEndDateChange={setEndDate}
        hasFilters={hasFilters}
        onClear={clearFilters}
      />

      {query.isLoading ? (
        <PapersSkeleton />
      ) : query.isError ? (
        <div className="flex flex-col items-start gap-3 border-t border-hairline pt-8">
          <p className="text-[13.5px] text-muted-ink">试卷列表加载失败</p>
          <Button variant="outline" size="sm" onClick={() => query.refetch()}>
            重试
          </Button>
        </div>
      ) : papers.length === 0 ? (
        hasFilters ? (
          <NoMatchState onClear={clearFilters} />
        ) : (
          <EmptyState />
        )
      ) : (
        <>
          <div className="border-t border-hairline">
            {papers.map((paper) => (
              <PaperRow key={paper.paper_id} paper={paper} />
            ))}
          </div>
          {query.hasNextPage && (
            <div className="mt-4 flex">
              <Button
                variant="ghost"
                size="sm"
                disabled={query.isFetchingNextPage}
                onClick={() => query.fetchNextPage()}
              >
                {query.isFetchingNextPage ? '加载中…' : '加载更多'}
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  )
}

/** 筛选条：交卷状态（分段控件）+ 题型（Select）+ 日期区间 + 清除。 */
function FilterBar({
  status,
  onStatusChange,
  questionType,
  onQuestionTypeChange,
  startDate,
  onStartDateChange,
  endDate,
  onEndDateChange,
  hasFilters,
  onClear,
}: {
  status: StatusFilter
  onStatusChange: (v: StatusFilter) => void
  questionType: string
  onQuestionTypeChange: (v: string) => void
  startDate: string
  onStartDateChange: (v: string) => void
  endDate: string
  onEndDateChange: (v: string) => void
  hasFilters: boolean
  onClear: () => void
}) {
  return (
    <div className="mb-4 flex flex-wrap items-center gap-x-5 gap-y-3">
      {/* 交卷状态：3 段分段控件（比下拉更直观，契合极简行式审美） */}
      <div className="inline-flex items-center rounded-lg border border-ink-20 p-0.5">
        {STATUS_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            type="button"
            onClick={() => onStatusChange(opt.value)}
            className={cn(
              'rounded-[7px] px-3 py-1 font-ui text-[12.5px] transition-colors',
              status === opt.value
                ? 'bg-tint text-ink'
                : 'text-quiet hover:text-ink',
            )}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {/* 题型 */}
      <Select
        value={questionType || 'all'}
        onValueChange={(v) => onQuestionTypeChange(v === 'all' ? '' : v)}
      >
        <SelectTrigger size="sm" className="border-ink-20 font-ui text-[12.5px]">
          <SelectValue placeholder="全部题型" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">全部题型</SelectItem>
          {Object.entries(TYPE_LABELS).map(([type, label]) => (
            <SelectItem key={type} value={type}>
              {label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {/* 日期区间 */}
      <div className="inline-flex items-center gap-1.5 font-ui text-[12.5px] text-quiet">
        <span>起</span>
        <input
          type="date"
          value={startDate}
          max={endDate || undefined}
          onChange={(e) => onStartDateChange(e.target.value)}
          className="rounded-lg border border-ink-20 px-2 py-1 text-ink outline-none transition-colors focus:border-accent"
        />
        <span>止</span>
        <input
          type="date"
          value={endDate}
          min={startDate || undefined}
          onChange={(e) => onEndDateChange(e.target.value)}
          className="rounded-lg border border-ink-20 px-2 py-1 text-ink outline-none transition-colors focus:border-accent"
        />
      </div>

      {hasFilters && (
        <button
          type="button"
          onClick={onClear}
          className="font-ui text-[12.5px] text-quiet underline-offset-4 transition-colors hover:text-ink hover:underline"
        >
          清除筛选
        </button>
      )}
    </div>
  )
}

function PaperRow({ paper }: { paper: PaperListItem }) {
  const d = new Date(paper.generated_at)
  const date = `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  return (
    <Link
      to={PATHS.paper(paper.paper_id)}
      className="grid grid-cols-[110px_minmax(0,1fr)_auto] items-center gap-4 border-b border-hairline px-2 py-[18px] transition-colors hover:bg-tint max-sm:grid-cols-[minmax(0,1fr)_auto]"
    >
      <span className="font-mono text-[12.5px] text-quiet max-sm:hidden">{date}</span>
      <div className="flex min-w-0 flex-col gap-1">
        <span className="truncate text-[15.5px] text-ink">{paper.title}</span>
        <span className="font-ui text-[12.5px] tabular-nums text-quiet">{paper.total_questions} 题</span>
      </div>
      <span
        className={cn(
          'shrink-0 font-ui text-[13px]',
          paper.submitted ? 'text-ink' : 'text-quiet',
        )}
      >
        {paper.submitted ? '已交卷' : '未作答'}
      </span>
    </Link>
  )
}

/** 空态（教学式）：指向唯一下一步——去生成第一份卷。 */
function EmptyState() {
  return (
    <div className="flex flex-col items-start gap-2 border-t border-hairline pt-8">
      <p className="text-[17px] text-ink">还没有试卷</p>
      <p className="text-[13.5px] text-muted-ink">
        用一句话描述想练的题型或考点，生成你的第一份卷
      </p>
      <Button asChild className="mt-3">
        <Link to={PATHS.dashboard}>去出卷</Link>
      </Button>
    </div>
  )
}

/** 筛选无命中：与默认空态区分，给出清除筛选而非去出卷。 */
function NoMatchState({ onClear }: { onClear: () => void }) {
  return (
    <div className="flex flex-col items-start gap-2 border-t border-hairline pt-8">
      <p className="text-[17px] text-ink">没有符合条件的试卷</p>
      <p className="text-[13.5px] text-muted-ink">换个筛选条件，或清除筛选看全部试卷</p>
      <Button variant="outline" size="sm" className="mt-3" onClick={onClear}>
        清除筛选
      </Button>
    </div>
  )
}

function PapersSkeleton() {
  return (
    <div className="flex flex-col border-t border-hairline">
      {Array.from({ length: 4 }, (_, i) => (
        <div key={i} className="flex items-center justify-between gap-4 border-b border-hairline px-2 py-[18px]">
          <div className="flex w-full flex-col gap-2">
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-3 w-1/2" />
          </div>
          <Skeleton className="h-4 w-12 shrink-0" />
        </div>
      ))}
    </div>
  )
}
