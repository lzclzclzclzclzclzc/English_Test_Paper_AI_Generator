import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listMindmaps, createMindmap, deleteMindmap, updateMindmap } from '@/api/agent'
import type { MindmapListItem } from '@/types/api'
import { PATHS } from '@/lib/paths'
import { PageHeader } from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { toastApiError } from '@/lib/errors'

const PAGE_SIZE = 20

/** 思维导图：行式列表 + 新建 + 行内重命名/删除。 */
export function MindmapsPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()

  const query = useInfiniteQuery({
    queryKey: ['mindmaps', 'list'],
    queryFn: ({ pageParam }) => listMindmaps(PAGE_SIZE, pageParam),
    initialPageParam: 0,
    getNextPageParam: (last, _all, lastOffset) =>
      last.items.length === PAGE_SIZE ? lastOffset + PAGE_SIZE : undefined,
  })

  const createMut = useMutation({
    mutationFn: () => createMindmap('未命名思维导图', '# 未命名思维导图\n## 分支一\n- 要点'),
    onSuccess: (res) => navigate(PATHS.mindmap(res.id)),
    onError: toastApiError,
  })

  const items = query.data?.pages.flatMap((p) => p.items) ?? []

  return (
    <div className="max-w-[56rem]">
      <PageHeader
        title="思维导图"
        intro="用思维导图整理语法和知识点。可以让学习助手帮你生成，也可以自己新建、编辑。"
      />

      <div className="mb-4 flex">
        <Button size="sm" disabled={createMut.isPending} onClick={() => createMut.mutate()}>
          ＋ 新建思维导图
        </Button>
      </div>

      {query.isLoading ? (
        <ListSkeleton />
      ) : query.isError ? (
        <div className="flex flex-col items-start gap-3 border-t border-hairline pt-8">
          <p className="text-[13.5px] text-muted-ink">列表加载失败</p>
          <Button variant="outline" size="sm" onClick={() => query.refetch()}>重试</Button>
        </div>
      ) : items.length === 0 ? (
        <EmptyState onCreate={() => createMut.mutate()} />
      ) : (
        <>
          <div className="border-t border-hairline">
            {items.map((m) => (
              <MindmapRow key={m.id} m={m} onChanged={() => qc.invalidateQueries({ queryKey: ['mindmaps', 'list'] })} />
            ))}
          </div>
          {query.hasNextPage && (
            <div className="mt-4 flex">
              <Button variant="ghost" size="sm" disabled={query.isFetchingNextPage}
                onClick={() => query.fetchNextPage()}>
                {query.isFetchingNextPage ? '加载中…' : '加载更多'}
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  )
}

function MindmapRow({ m, onChanged }: { m: MindmapListItem; onChanged: () => void }) {
  const [renaming, setRenaming] = useState(false)
  const [name, setName] = useState(m.title)
  const d = new Date(m.updated_at)
  const date = `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`

  const renameMut = useMutation({
    mutationFn: () => updateMindmap(m.id, { title: name.trim() || m.title }),
    onSuccess: () => { setRenaming(false); onChanged() },
    onError: toastApiError,
  })
  const deleteMut = useMutation({
    mutationFn: () => deleteMindmap(m.id),
    onSuccess: onChanged,
    onError: toastApiError,
  })
  // 进入重命名时才种下当前标题，避免行数据在后台更新后 name 变陈旧
  const startRename = () => { setName(m.title); setRenaming(true) }

  return (
    <div className="grid grid-cols-[110px_minmax(0,1fr)_auto] items-center gap-4 border-b border-hairline px-2 py-[18px] transition-colors hover:bg-tint max-sm:grid-cols-[minmax(0,1fr)_auto]">
      <span className="font-mono text-[12.5px] text-quiet max-sm:hidden">{date}</span>
      {renaming ? (
        <input
          autoFocus value={name} onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') renameMut.mutate() }}
          className="min-w-0 border border-ink-20 px-2 py-1 text-[15px] text-ink outline-none focus:border-accent"
          style={{ borderRadius: '8px' }}
        />
      ) : (
        <Link to={PATHS.mindmap(m.id)} className="min-w-0">
          <span className="block truncate text-[15.5px] text-ink">{m.title}</span>
          {m.knowledge_point && (
            <span className="font-ui text-[12.5px] text-quiet">{m.knowledge_point}</span>
          )}
        </Link>
      )}
      <div className="flex shrink-0 items-center gap-3 font-ui text-[13px]">
        {renaming ? (
          <>
            <button className="text-accent disabled:opacity-50" disabled={renameMut.isPending}
              onClick={() => renameMut.mutate()}>保存</button>
            <button className="text-quiet" onClick={() => setRenaming(false)}>取消</button>
          </>
        ) : (
          <>
            <button className="text-quiet hover:text-accent" onClick={startRename}>重命名</button>
            <button className="text-quiet hover:text-accent disabled:opacity-50" disabled={deleteMut.isPending}
              onClick={() => { if (confirm('确定删除这张思维导图？')) deleteMut.mutate() }}>
              删除
            </button>
          </>
        )}
      </div>
    </div>
  )
}

function EmptyState({ onCreate }: { onCreate: () => void }) {
  return (
    <div className="flex flex-col items-start gap-2 border-t border-hairline pt-8">
      <p className="text-[17px] text-ink">还没有思维导图</p>
      <p className="text-[13.5px] text-muted-ink">
        让学习助手"用思维导图讲讲……"，或直接新建一张
      </p>
      <Button className="mt-3" onClick={onCreate}>新建思维导图</Button>
    </div>
  )
}

function ListSkeleton() {
  return (
    <div className="flex flex-col border-t border-hairline">
      {Array.from({ length: 4 }, (_, i) => (
        <div key={i} className="flex items-center justify-between gap-4 border-b border-hairline px-2 py-[18px]">
          <div className="flex w-full flex-col gap-2">
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-3 w-1/2" />
          </div>
          <Skeleton className="h-4 w-16 shrink-0" />
        </div>
      ))}
    </div>
  )
}
