import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { listOrders } from '@/api/admin'
import { cn } from '@/lib/utils'

const STATUS_OPTIONS = [
  { value: '', label: '全部' },
  { value: 'CREATED', label: 'CREATED' },
  { value: 'PAID', label: 'PAID' },
  { value: 'EXPIRED', label: 'EXPIRED' },
  { value: 'CLOSED', label: 'CLOSED' },
] as const

export function AdminOrdersPage() {
  const [status, setStatus] = useState('')
  const orders = useQuery({
    queryKey: ['admin', 'orders', status],
    queryFn: () => listOrders(status),
  })

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-[20px] text-ink [font-family:var(--font-display)]">订单</h1>

      <select
        value={status}
        onChange={(e) => setStatus(e.target.value)}
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
          <thead className="bg-wash/60 text-left text-muted-ink">
            <tr>
              <th className="px-3 py-2 font-medium">订单号</th>
              <th className="px-3 py-2 font-medium">用户</th>
              <th className="px-3 py-2 font-medium">套餐</th>
              <th className="px-3 py-2 font-medium">金额</th>
              <th className="px-3 py-2 font-medium">状态</th>
              <th className="px-3 py-2 font-medium">创建时间</th>
            </tr>
          </thead>
          <tbody>
            {(orders.data?.items ?? []).map((o) => (
              <tr key={o.out_trade_no} className="border-t border-hairline hover:bg-tint/40">
                <td className="px-3 py-2 text-ink">{o.out_trade_no}</td>
                <td className="px-3 py-2 text-muted-ink">{o.user_id}</td>
                <td className="px-3 py-2 text-muted-ink">{o.plan_id}</td>
                <td className="px-3 py-2 text-muted-ink">
                  ¥{(o.amount_cents / 100).toFixed(2)}
                </td>
                <td className="px-3 py-2 text-muted-ink">{o.status}</td>
                <td className="px-3 py-2 text-muted-ink">
                  {o.created_at.slice(0, 19).replace('T', ' ')}
                </td>
              </tr>
            ))}
            {orders.data && orders.data.items.length === 0 && (
              <tr>
                <td colSpan={6} className="px-3 py-6 text-center text-quiet">
                  暂无订单
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
