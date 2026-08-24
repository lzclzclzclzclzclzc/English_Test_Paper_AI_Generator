import { useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { listAuditLogs } from '@/api/admin'
import { displayName } from '@/lib/adminDisplay'
import { cn } from '@/lib/utils'
import { Input } from '@/components/ui/input'
import { Pagination } from '@/components/admin/Pagination'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

const PAGE_SIZE = 50

/** 动作类型 → 中文标签（Spec H 5.3）。导出供逻辑测试与复用。 */
export const ACTION_LABELS: Record<string, string> = {
  set_role: '改角色',
  reset_password: '重置密码',
  ban: '封禁',
  unban: '解封',
  adjust_credits: '调整积分',
  grant_membership: '开通会员（历史）',
  revoke_membership: '撤销会员（历史）',
}

/** detail_json 中的关键值（days/role 等）以标签展示。 */
function DetailTags({ detail }: { detail: Record<string, unknown> | null }) {
  if (!detail) return null
  const entries = Object.entries(detail).filter(([k]) => k !== 'new_password')
  if (entries.length === 0) return <span className="text-quiet">—</span>
  return (
    <span className="flex flex-wrap gap-1">
      {entries.map(([k, v]) => (
        <span
          key={k}
          className="rounded-sm border border-hairline bg-wash/60 px-1.5 py-px font-ui text-[11px] text-muted-ink"
        >
          {k === 'days' ? `${v} 天` : `${k}: ${String(v)}`}
        </span>
      ))}
    </span>
  )
}

/** 审计日志（Spec H D3）：管理员写操作留痕，按时间倒序分页浏览。 */
export function AdminAuditPage() {
  const [actor, setActor] = useState('')
  const [action, setAction] = useState('')
  const [page, setPage] = useState(1)
  const audit = useQuery({
    queryKey: ['admin', 'audit', actor, action, page],
    queryFn: () => listAuditLogs(actor, action, PAGE_SIZE, (page - 1) * PAGE_SIZE),
    placeholderData: keepPreviousData,
  })
  const total = audit.data?.total ?? 0
  const items = audit.data?.items ?? []

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-[20px] text-ink [font-family:var(--font-display)]">审计日志</h1>

      {/* 筛选栏：操作者（用户 ID）+ 动作类型 */}
      <div className="flex flex-wrap items-center gap-2">
        <Input
          aria-label="操作者用户 ID"
          className="h-8 w-64 font-ui text-[12.5px]"
          placeholder="操作者用户 ID…"
          value={actor}
          onChange={(e) => {
            setActor(e.target.value)
            setPage(1)
          }}
        />
        <Select
          value={action || 'all'}
          onValueChange={(v) => {
            setAction(v === 'all' ? '' : v)
            setPage(1)
          }}
        >
          <SelectTrigger size="sm" aria-label="动作类型筛选" className="w-[140px] border-ink-20 font-ui text-[12.5px]">
            <SelectValue placeholder="全部动作" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部动作</SelectItem>
            {Object.entries(ACTION_LABELS).map(([a, label]) => (
              <SelectItem key={a} value={a}>
                {label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className={cn('overflow-x-auto rounded-md border border-hairline', audit.isFetching && 'opacity-60')}>
        <table className="w-full text-left text-[13px]">
          <thead className="bg-wash/60 font-ui text-muted-ink">
            <tr>
              <th className="px-3 py-2 font-normal">时间</th>
              <th className="px-3 py-2 font-normal">操作者</th>
              <th className="px-3 py-2 font-normal">动作</th>
              <th className="px-3 py-2 font-normal">对象</th>
              <th className="px-3 py-2 font-normal">详情</th>
            </tr>
          </thead>
          <tbody>
            {items.map((a) => (
              <tr key={a.id} className="border-t border-hairline hover:bg-tint/40">
                <td className="whitespace-nowrap px-3 py-2 text-muted-ink">
                  {a.created_at.slice(0, 19).replace('T', ' ')}
                </td>
                <td className="px-3 py-2 text-ink">{displayName(a.actor_username)}</td>
                <td className="px-3 py-2 text-ink">{ACTION_LABELS[a.action] ?? a.action}</td>
                <td className="px-3 py-2 text-ink">{displayName(a.target_username)}</td>
                <td className="px-3 py-2">
                  <DetailTags detail={a.detail} />
                </td>
              </tr>
            ))}
            {audit.isLoading && (
              <tr>
                <td colSpan={5} className="px-3 py-6 text-center text-quiet">
                  加载中…
                </td>
              </tr>
            )}
            {audit.isError && (
              <tr>
                <td colSpan={5} className="px-3 py-6 text-center text-muted-ink">
                  日志加载失败{' '}
                  <button className="text-accent hover:underline" onClick={() => audit.refetch()}>
                    重试
                  </button>
                </td>
              </tr>
            )}
            {!audit.isLoading && !audit.isError && items.length === 0 && (
              <tr>
                <td colSpan={5} className="px-3 py-6 text-center text-quiet">
                  暂无日志
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
