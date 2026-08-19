import { useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { listUsers } from '@/api/admin'
import { Pagination } from '@/components/admin/Pagination'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

const PAGE_SIZE = 50

const STATUS_OPTIONS = [
  { value: '', label: '全部状态' },
  { value: 'active', label: '正常' },
  { value: 'banned', label: '已封禁' },
] as const

/** 可点击的排序表头：点击切换到该列（当前列再点无翻转，保持简单）。 */
function SortTh({
  label,
  sortKey,
  sort,
  onSort,
}: {
  label: string
  sortKey: string
  sort: string
  onSort: (key: string) => void
}) {
  const active = sort === sortKey
  return (
    <th
      className={cn('cursor-pointer select-none px-3 py-2', active && 'text-accent')}
      onClick={() => onSort(sortKey)}
    >
      {label}
      {active ? ' ↓' : ''}
    </th>
  )
}

export function AdminUsersPage() {
  const [q, setQ] = useState('')
  const [status, setStatus] = useState('')
  const [sort, setSort] = useState('created_at')
  const [page, setPage] = useState(1)
  const users = useQuery({
    queryKey: ['admin', 'users', q, status, sort, page],
    queryFn: () => listUsers(q, PAGE_SIZE, (page - 1) * PAGE_SIZE, status, sort),
    placeholderData: keepPreviousData,
  })
  const total = users.data?.total ?? 0

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-[20px] text-ink [font-family:var(--font-display)]">用户</h1>
      <div className="flex items-center gap-2">
        <Input
          placeholder="搜索用户名…"
          value={q}
          onChange={(e) => {
            setQ(e.target.value)
            setPage(1)
          }}
          className="max-w-[280px]"
        />
        <select
          value={status}
          onChange={(e) => {
            setStatus(e.target.value)
            setPage(1)
          }}
          className={cn(
            'h-8 rounded-lg border border-hairline bg-transparent px-2.5 py-1',
            'text-[13px] text-ink outline-none focus-visible:border-ring',
          )}
        >
          {STATUS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>
      <div className="overflow-hidden rounded-md border border-hairline">
        <table className="w-full text-[13px]">
          <thead className="bg-wash/60 text-left font-ui text-muted-ink">
            <tr>
              <th className="px-3 py-2">用户名</th>
              <SortTh label="注册" sortKey="created_at" sort={sort} onSort={setSort} />
              <th className="px-3 py-2">角色</th>
              <th className="px-3 py-2">状态</th>
              <SortTh label="试卷" sortKey="paper_count" sort={sort} onSort={setSort} />
              <SortTh label="做题数" sortKey="attempt_count" sort={sort} onSort={setSort} />
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {(users.data?.items ?? []).map((u) => (
              <tr key={u.id} className="border-t border-hairline hover:bg-tint/40">
                <td className="px-3 py-2 text-ink">{u.username}</td>
                <td className="px-3 py-2 text-muted-ink">{u.created_at.slice(0, 10)}</td>
                <td className="px-3 py-2 text-muted-ink">{u.role === 'admin' ? '管理员' : '用户'}</td>
                <td className="px-3 py-2 text-muted-ink">{u.status === 'banned' ? '已封禁' : '正常'}</td>
                <td className="px-3 py-2 text-muted-ink">{u.paper_count}</td>
                <td className="px-3 py-2 text-muted-ink">{u.attempt_count}</td>
                <td className="px-3 py-2 text-right">
                  <Link to={`/admin/users/${u.id}`} className="text-accent hover:underline">
                    详情
                  </Link>
                </td>
              </tr>
            ))}
            {users.isLoading && (
              <tr>
                <td colSpan={7} className="px-3 py-6 text-center text-quiet">
                  加载中…
                </td>
              </tr>
            )}
            {users.isError && (
              <tr>
                <td colSpan={7} className="px-3 py-6 text-center text-muted-ink">
                  用户列表加载失败{' '}
                  <button className="text-accent hover:underline" onClick={() => users.refetch()}>
                    重试
                  </button>
                </td>
              </tr>
            )}
            {!users.isLoading && !users.isError && users.data && users.data.items.length === 0 && (
              <tr>
                <td colSpan={7} className="px-3 py-6 text-center text-quiet">
                  没有匹配的用户
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <Pagination page={page} pageSize={PAGE_SIZE} total={total} onChange={setPage} />
    </div>
  )
}
