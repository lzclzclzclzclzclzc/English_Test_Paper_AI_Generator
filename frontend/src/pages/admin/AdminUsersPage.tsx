import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { listUsers } from '@/api/admin'
import { Input } from '@/components/ui/input'

export function AdminUsersPage() {
  const [q, setQ] = useState('')
  const users = useQuery({ queryKey: ['admin', 'users', q], queryFn: () => listUsers(q) })
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-[20px] text-ink [font-family:var(--font-display)]">用户</h1>
      <Input
        placeholder="搜索用户名…"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        className="max-w-[280px]"
      />
      <div className="overflow-hidden rounded-md border border-hairline">
        <table className="w-full text-[13px]">
          <thead className="bg-wash/60 text-left text-muted-ink">
            <tr>
              <th className="px-3 py-2 font-medium">用户名</th>
              <th className="px-3 py-2 font-medium">注册</th>
              <th className="px-3 py-2 font-medium">角色</th>
              <th className="px-3 py-2 font-medium">状态</th>
              <th className="px-3 py-2 font-medium">试卷</th>
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
                <td className="px-3 py-2 text-right">
                  <Link to={`/admin/users/${u.id}`} className="text-accent hover:underline">
                    详情
                  </Link>
                </td>
              </tr>
            ))}
            {users.isLoading && (
              <tr>
                <td colSpan={6} className="px-3 py-6 text-center text-quiet">
                  加载中…
                </td>
              </tr>
            )}
            {users.isError && (
              <tr>
                <td colSpan={6} className="px-3 py-6 text-center text-muted-ink">
                  用户列表加载失败{' '}
                  <button className="text-accent hover:underline" onClick={() => users.refetch()}>
                    重试
                  </button>
                </td>
              </tr>
            )}
            {!users.isLoading && !users.isError && users.data && users.data.items.length === 0 && (
              <tr>
                <td colSpan={6} className="px-3 py-6 text-center text-quiet">
                  没有匹配的用户
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
