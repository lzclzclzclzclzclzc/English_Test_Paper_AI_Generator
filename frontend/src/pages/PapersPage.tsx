import { Link } from 'react-router-dom'
import { useInfiniteQuery } from '@tanstack/react-query'
import { listPapers } from '@/api/papers'
import type { PaperListItem } from '@/types/api'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'

const PAGE_SIZE = 20

/** 历史试卷（handoff 第 8 屏）：无卡片的行式列表，整行可点。满页即认为还有下一页。 */
export function PapersPage() {
  const query = useInfiniteQuery({
    queryKey: ['papers', 'list'],
    queryFn: ({ pageParam }) => listPapers(PAGE_SIZE, pageParam),
    initialPageParam: 0,
    getNextPageParam: (last, _all, lastOffset) =>
      last.items.length === PAGE_SIZE ? lastOffset + PAGE_SIZE : undefined,
  })

  const papers = query.data?.pages.flatMap((p) => p.items) ?? []

  return (
    <div className="max-w-[56rem]">
      <p className="text-[11px] tracking-[0.1em] text-quiet">GET /API/PAPERS</p>
      <div className="mb-10 mt-3 flex flex-col gap-3">
        <h1 className="text-[30px] font-normal leading-snug text-ink">历史试卷</h1>
        <p className="max-w-[42rem] text-[15px] leading-[1.9] text-muted-ink">
          生成过的卷都在这里，未交的随时开卷，交过的回来复盘。重新生成会产生新
          paper_id，旧试卷保留。
        </p>
      </div>

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
        <EmptyState />
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

function PaperRow({ paper }: { paper: PaperListItem }) {
  const d = new Date(paper.generated_at)
  const date = `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  return (
    <Link
      to={`/papers/${paper.paper_id}`}
      className="grid grid-cols-[110px_minmax(0,1fr)_auto] items-center gap-4 border-b border-hairline px-2 py-[18px] transition-colors hover:bg-tint max-sm:grid-cols-[minmax(0,1fr)_auto]"
    >
      <span className="font-mono text-[12.5px] text-quiet max-sm:hidden">{date}</span>
      <div className="flex min-w-0 flex-col gap-1">
        <span className="truncate text-[15.5px] text-ink">{paper.title}</span>
        <span className="text-[12.5px] text-quiet">
          {paper.total_questions} 题 · 满分 {paper.total_score} 分
        </span>
      </div>
      <span
        className={cn(
          'shrink-0 text-[13px]',
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
        <Link to="/">去出卷</Link>
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
