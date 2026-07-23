import { Link } from 'react-router-dom'
import { useInfiniteQuery } from '@tanstack/react-query'
import { listPapers } from '@/api/papers'
import type { PaperListItem } from '@/types/api'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'

const PAGE_SIZE = 20

/** 列表接口只有摘要没有总数：满页即认为还有下一页（Spec D 缓存键 ['papers','list']）。 */
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
    <div className="mx-auto flex max-w-[880px] flex-col gap-6 px-6 pt-12">
      <div className="flex flex-col gap-1">
        <h1 className="font-serif text-2xl font-bold text-foreground">我的试卷</h1>
        <p className="text-[13.5px] text-text-mid">
          生成过的卷都在这里，未交的随时开卷，交过的回来复盘
        </p>
      </div>

      {query.isLoading ? (
        <PapersSkeleton />
      ) : query.isError ? (
        <div className="flex flex-col items-center gap-3 py-16">
          <p className="text-[13.5px] text-text-mid">试卷列表加载失败</p>
          <Button variant="outline" size="sm" onClick={() => query.refetch()}>
            重试
          </Button>
        </div>
      ) : papers.length === 0 ? (
        <EmptyState />
      ) : (
        <>
          <ul className="divide-y divide-line-soft rounded-md border border-line bg-sheet">
            {papers.map((paper) => (
              <PaperRow key={paper.paper_id} paper={paper} />
            ))}
          </ul>
          {query.hasNextPage && (
            <div className="flex justify-center">
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
  const generatedAt = new Date(paper.generated_at).toLocaleString('zh-CN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
  return (
    <li>
      <Link
        to={`/papers/${paper.paper_id}`}
        className="flex items-center justify-between gap-4 px-5 py-3.5 transition-colors hover:bg-[#faf8f3]"
      >
        <div className="flex min-w-0 flex-col gap-1">
          <span className="truncate font-serif text-[15px] font-semibold text-foreground">
            {paper.title}
          </span>
          <span className="text-[12.5px] text-text-mid">
            {generatedAt} · {paper.total_questions} 题
          </span>
        </div>
        <span
          className={cn(
            'shrink-0 rounded-full px-2.5 py-0.5 text-xs',
            paper.submitted
              ? 'bg-ink-wash font-medium text-ink'
              : 'border border-line-strong text-text-mid',
          )}
        >
          {paper.submitted ? '已交卷' : '未作答'}
        </span>
      </Link>
    </li>
  )
}

/** 空态（教学式）：指向唯一下一步——去生成第一份卷。 */
function EmptyState() {
  return (
    <div className="flex flex-col items-center gap-2 rounded-md border border-dashed border-line-strong px-6 py-20 text-center">
      <p className="font-serif text-lg font-bold text-foreground">还没有试卷</p>
      <p className="text-[13.5px] text-text-mid">
        用一句话描述想练的题型或考点，生成你的第一份卷
      </p>
      <Button asChild className="mt-3 px-6">
        <Link to="/">去出卷</Link>
      </Button>
    </div>
  )
}

function PapersSkeleton() {
  return (
    <div className="flex flex-col divide-y divide-line-soft rounded-md border border-line bg-sheet">
      {Array.from({ length: 4 }, (_, i) => (
        <div key={i} className="flex items-center justify-between gap-4 px-5 py-3.5">
          <div className="flex w-full flex-col gap-2">
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-3 w-1/2" />
          </div>
          <Skeleton className="h-5 w-14 shrink-0 rounded-full" />
        </div>
      ))}
    </div>
  )
}
