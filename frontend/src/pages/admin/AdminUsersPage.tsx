import { useState, type ReactNode } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { ListFilter } from 'lucide-react'
import { listUsers } from '@/api/admin'
import { Pagination } from '@/components/admin/Pagination'
import { Input } from '@/components/ui/input'
import { Popover, PopoverClose, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
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

/** 表头右侧的筛选漏斗：命中筛选时变赤陶色。面板通过 Portal 渲染，不被表格 overflow 裁切。 */
function FilterMenu({
  active,
  label,
  className,
  children,
}: {
  active: boolean
  label: string
  className?: string
  children: ReactNode
}) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={`筛选${label}`}
          className={cn('rounded p-0.5 transition-colors hover:text-ink', active ? 'text-accent' : 'text-quiet')}
        >
          <ListFilter className="size-3.5" />
        </button>
      </PopoverTrigger>
      <PopoverContent className={className}>{children}</PopoverContent>
    </Popover>
  )
}

/** 单选选项列表（状态 / 角色）：点选即回填并关闭面板。 */
function OptionList({
  value,
  options,
  onPick,
}: {
  value: string
  options: readonly { value: string; label: string }[]
  onPick: (v: string) => void
}) {
  return (
    <div className="flex flex-col">
      {options.map((o) => (
        <PopoverClose asChild key={o.value}>
          <button
            type="button"
            onClick={() => onPick(o.value)}
            className={cn(
              'rounded px-2 py-1.5 text-left hover:bg-tint/40',
              value === o.value ? 'text-accent' : 'text-ink',
            )}
          >
            {o.label}
          </button>
        </PopoverClose>
      ))}
    </div>
  )
}

/** 可点击排序的表头内容：点击切换到该列（当前列再点无翻转，保持简单）。 */
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

const dateInputClass =
  'mt-1 block h-8 w-full rounded-md border border-hairline bg-transparent px-2 text-[13px] text-ink outline-none focus-visible:border-ring'

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
                    <Input
                      autoFocus
                      placeholder="搜索用户名…"
                      value={q}
                      onChange={(e) => {
                        setQ(e.target.value)
                        setPage(1)
                      }}
                      className="h-8"
                    />
                    {q && (
                      <button
                        type="button"
                        className="mt-2 text-[12px] text-quiet hover:text-ink"
                        onClick={() => {
                          setQ('')
                          setPage(1)
                        }}
                      >
                        清除
                      </button>
                    )}
                  </FilterMenu>
                </div>
              </th>
              <th className={cn('px-3 py-2', sort === 'created_at' && 'text-accent')}>
                <div className="flex items-center gap-1">
                  <SortLabel label="注册" sortKey="created_at" sort={sort} onSort={setSort} />
                  <FilterMenu active={!!(createdFrom || createdTo)} label="注册日期">
                    <div className="flex flex-col gap-2">
                      <label className="text-[12px] text-quiet">
                        从
                        <input
                          type="date"
                          value={createdFrom}
                          max={createdTo || undefined}
                          onChange={(e) => {
                            setCreatedFrom(e.target.value)
                            setPage(1)
                          }}
                          className={dateInputClass}
                        />
                      </label>
                      <label className="text-[12px] text-quiet">
                        到
                        <input
                          type="date"
                          value={createdTo}
                          min={createdFrom || undefined}
                          onChange={(e) => {
                            setCreatedTo(e.target.value)
                            setPage(1)
                          }}
                          className={dateInputClass}
                        />
                      </label>
                      {(createdFrom || createdTo) && (
                        <button
                          type="button"
                          className="self-start text-[12px] text-quiet hover:text-ink"
                          onClick={() => {
                            setCreatedFrom('')
                            setCreatedTo('')
                            setPage(1)
                          }}
                        >
                          清除
                        </button>
                      )}
                    </div>
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
