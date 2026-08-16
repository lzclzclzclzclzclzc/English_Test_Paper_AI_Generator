import { useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import {
  Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { getRevenue, listOrders } from '@/api/admin'
import { Pagination } from '@/components/admin/Pagination'
import { displayName } from '@/lib/adminDisplay'
import { formatYuan } from '@/lib/money'
import { cn } from '@/lib/utils'

const ACCENT = '#ef4a2b'
const PAGE_SIZE = 50

const STATUS_OPTIONS = [
  { value: '', label: '全部' },
  { value: 'CREATED', label: 'CREATED' },
  { value: 'PAID', label: 'PAID' },
  { value: 'EXPIRED', label: 'EXPIRED' },
  { value: 'CLOSED', label: 'CLOSED' },
] as const

/** 收入统计区块（Spec H D1）：指标卡 + 按日收入折线 + 套餐分布。 */
function RevenuePanel() {
  const revenue = useQuery({ queryKey: ['admin', 'revenue'], queryFn: () => getRevenue(30) })
  const data = revenue.data
  if (revenue.isError || !data) return null
  const byDay = data.revenue_by_day.map((d) => ({
    day: d.day.slice(5),
    yuan: Math.round(d.cents) / 100,
  }))
  const byPlan = data.by_plan.map((p) => ({
    name: p.plan_id,
    yuan: Math.round(p.cents) / 100,
    orders: p.orders,
  }))
  return (
    <div className="rounded-md border border-hairline p-4">
      <div className="mb-3 flex flex-wrap items-baseline gap-x-6 gap-y-1">
        <div>
          <span className="text-[12px] text-quiet">累计收入</span>
          <span className="ml-2 font-ui text-[18px] font-bold tabular-nums text-ink">
            {formatYuan(data.total_cents)}
          </span>
        </div>
        <div className="text-[12px] text-quiet">
          近 30 天收入{' '}
          <span className="font-ui font-bold tabular-nums text-muted-ink">
            {formatYuan(data.revenue_by_day.reduce((s, d) => s + d.cents, 0))}
          </span>
        </div>
      </div>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div>
          <div className="mb-2 text-[13px] text-muted-ink">近 30 天每日收入（元）</div>
          {byDay.length === 0 ? (
            <p className="py-8 text-center text-[13px] text-quiet">暂无收入数据</p>
          ) : (
            <ResponsiveContainer width="100%" height={160}>
              <LineChart data={byDay}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--ink-10)" />
                <XAxis dataKey="day" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} width={40} />
                <Tooltip />
                <Line type="monotone" dataKey="yuan" name="收入(元)" stroke={ACCENT} strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
        <div>
          <div className="mb-2 text-[13px] text-muted-ink">套餐销售分布（近 30 天，元）</div>
          {byPlan.length === 0 ? (
            <p className="py-8 text-center text-[13px] text-quiet">暂无收入数据</p>
          ) : (
            <ResponsiveContainer width="100%" height={Math.max(120, byPlan.length * 44)}>
              <BarChart data={byPlan} margin={{ left: 8, right: 16 }}>
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} width={40} />
                <Tooltip />
                <Bar dataKey="yuan" name="收入(元)" fill={ACCENT} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>
    </div>
  )
}

export function AdminOrdersPage() {
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)
  const orders = useQuery({
    queryKey: ['admin', 'orders', status, page],
    queryFn: () => listOrders(status, PAGE_SIZE, (page - 1) * PAGE_SIZE),
    placeholderData: keepPreviousData,
  })
  const total = orders.data?.total ?? 0

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-[20px] text-ink [font-family:var(--font-display)]">订单</h1>

      <RevenuePanel />

      <select
        value={status}
        onChange={(e) => {
          setStatus(e.target.value)
          setPage(1)
        }}
        className={cn(
          'h-8 max-w-[200px] rounded-lg border border-hairline bg-transparent px-2.5 py-1',
          'text-[13px] text-ink outline-none focus-visible:border-ring',
        )}
      >
        {STATUS_OPTIONS.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>

      <div className="overflow-hidden rounded-md border border-hairline">
        <table className="w-full text-[13px]">
          <thead className="bg-wash/60 text-left font-ui text-muted-ink">
            <tr>
              <th className="px-3 py-2">订单号</th>
              <th className="px-3 py-2">用户</th>
              <th className="px-3 py-2">套餐</th>
              <th className="px-3 py-2">金额</th>
              <th className="px-3 py-2">状态</th>
              <th className="px-3 py-2">创建时间</th>
              <th className="px-3 py-2">支付时间</th>
            </tr>
          </thead>
          <tbody>
            {(orders.data?.items ?? []).map((o) => (
              <tr key={o.out_trade_no} className="border-t border-hairline hover:bg-tint/40">
                <td className="px-3 py-2 text-ink">{o.out_trade_no}</td>
                <td className="px-3 py-2 text-ink">
                  {displayName(o.username)}
                  <div className="text-[11px] text-quiet">{o.user_id}</div>
                </td>
                <td className="px-3 py-2 text-muted-ink">{o.plan_id}</td>
                <td className="px-3 py-2 text-muted-ink">
                  {formatYuan(o.amount_cents)}
                </td>
                <td className="px-3 py-2 text-muted-ink">{o.status}</td>
                <td className="px-3 py-2 text-muted-ink">
                  {o.created_at.slice(0, 19).replace('T', ' ')}
                </td>
                <td className="px-3 py-2 text-muted-ink">
                  {o.paid_at ? o.paid_at.slice(0, 19).replace('T', ' ') : '—'}
                </td>
              </tr>
            ))}
            {orders.isLoading && (
              <tr>
                <td colSpan={7} className="px-3 py-6 text-center text-quiet">
                  加载中…
                </td>
              </tr>
            )}
            {orders.isError && (
              <tr>
                <td colSpan={7} className="px-3 py-6 text-center text-muted-ink">
                  订单加载失败{' '}
                  <button className="text-accent hover:underline" onClick={() => orders.refetch()}>
                    重试
                  </button>
                </td>
              </tr>
            )}
            {!orders.isLoading && !orders.isError && orders.data && orders.data.items.length === 0 && (
              <tr>
                <td colSpan={7} className="px-3 py-6 text-center text-quiet">
                  暂无订单
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
