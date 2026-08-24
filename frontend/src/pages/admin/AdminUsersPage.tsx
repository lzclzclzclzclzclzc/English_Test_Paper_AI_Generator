import { useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { listUsers } from '@/api/admin'
import { Pagination } from '@/components/admin/Pagination'
import { DateRangeFilter, FilterMenu, OptionList, SearchFilter } from '@/components/admin/HeaderFilter'
import { cn } from '@/lib/utils'

const PAGE_SIZE = 50

const STATUS_OPTIONS = [
  { value: '', label: '全部状态' },
  { value: 'active', label: '正常' },
  { value: 'banned', label: '已封禁' },
] as const

const ROLE_OPTIONS = [
  { value: '', label: '全部角色' },
  { value: 'user', label: '用户' },
  { value: 'admin', label: '管理员' },
] as const

/** 可点击排序的表头文字：点击切换到该列（当前列再点无翻转，保持简单）。 */
function SortLabel({
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
    <span
      className={cn('cursor-pointer select-none', active && 'text-accent')}
      onClick={() => onSort(sortKey)}
    >
      {label}
      {active ? ' ↓' : ''}
    </span>
  )
}

export function AdminUsersPage() {
  const [q, setQ] = useState('')
  const [status, setStatus] = useState('')
  const [role, setRole] = useState('')
  const [createdFrom, setCreatedFrom] = useState('')
  const [createdTo, setCreatedTo] = useState('')
  const [sort, setSort] = useState('created_at')
  const [page, setPage] = useState(1)

  const users = useQuery({
    queryKey: ['admin', 'users', q, status, role, createdFrom, createdTo, sort, page],
    queryFn: () =>
      listUsers(q, PAGE_SIZE, (page - 1) * PAGE_SIZE, status, sort, role, createdFrom, createdTo),
    placeholderData: keepPreviousData,
  })
  const total = users.data?.total ?? 0

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-[20px] text-ink [font-family:var(--font-display)]">用户</h1>
      <div className="overflow-hidden rounded-md border border-hairline">
        <table className="w-full text-[13px]">
          <thead className="bg-wash/60 text-left font-ui text-muted-ink">
            <tr>
              <th className="px-3 py-2">
                <div className="flex items-center gap-1">
                  <span>用户名</span>
                  <FilterMenu active={q !== ''} label="用户名" className="w-64">
                    <SearchFilter
                      value={q}
                      placeholder="搜索用户名…"
                      onChange={(v) => {
                        setQ(v)
                        setPage(1)
                      }}
                    />
                  </FilterMenu>
                </div>
              </th>
              <th className={cn('px-3 py-2', sort === 'created_at' && 'text-accent')}>
                <div className="flex items-center gap-1">
                  <SortLabel label="注册" sortKey="created_at" sort={sort} onSort={setSort} />
                  <FilterMenu active={!!(createdFrom || createdTo)} label="注册日期">
                    <DateRangeFilter
                      from={createdFrom}
                      to={createdTo}
                      onChange={(f, t) => {
                        setCreatedFrom(f)
                        setCreatedTo(t)
                        setPage(1)
                      }}
                    />
                  </FilterMenu>
                </div>
              </th>
              <th className="px-3 py-2">
                <div className="flex items-center gap-1">
                  <span>角色</span>
                  <FilterMenu active={role !== ''} label="角色" className="w-40">
                    <OptionList
                      value={role}
                      options={ROLE_OPTIONS}
                      onPick={(v) => {
                        setRole(v)
                        setPage(1)
                      }}
                    />
                  </FilterMenu>
                </div>
              </th>
              <th className="px-3 py-2">
                <div className="flex items-center gap-1">
                  <span>状态</span>
                  <FilterMenu active={status !== ''} label="状态" className="w-40">
                    <OptionList
                      value={status}
                      options={STATUS_OPTIONS}
                      onPick={(v) => {
                        setStatus(v)
                        setPage(1)
                      }}
                    />
                  </FilterMenu>
                </div>
              </th>
              <th className="cursor-pointer select-none px-3 py-2" onClick={() => setSort('paper_count')}>
                <span className={cn(sort === 'paper_count' && 'text-accent')}>
                  试卷{sort === 'paper_count' ? ' ↓' : ''}
                </span>
              </th>
              <th className="cursor-pointer select-none px-3 py-2" onClick={() => setSort('attempt_count')}>
                <span className={cn(sort === 'attempt_count' && 'text-accent')}>
                  做题数{sort === 'attempt_count' ? ' ↓' : ''}
                </span>
              </th>
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
