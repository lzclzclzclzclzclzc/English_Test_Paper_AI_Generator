import { useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { listOrders } from '@/api/admin'
import { Pagination } from '@/components/admin/Pagination'
import { DateRangeFilter, FilterMenu, OptionList, SearchFilter } from '@/components/admin/HeaderFilter'
import { displayName } from '@/lib/adminDisplay'
import { formatYuan } from '@/lib/money'

const PAGE_SIZE = 50

const STATUS_OPTIONS = [
  { value: '', label: '全部状态' },
  { value: 'CREATED', label: 'CREATED' },
  { value: 'PAID', label: 'PAID' },
  { value: 'EXPIRED', label: 'EXPIRED' },
  { value: 'CLOSED', label: 'CLOSED' },
] as const

const PACK_OPTIONS = [
  { value: '', label: '全部积分包' },
  { value: 'starter', label: '入门' },
  { value: 'standard', label: '标准' },
  { value: 'annual', label: '畅练' },
] as const

export function AdminOrdersPage() {
  const [status, setStatus] = useState('')
  const [orderNo, setOrderNo] = useState('')
  const [userQ, setUserQ] = useState('')
  const [packId, setPackId] = useState('')
  const [createdFrom, setCreatedFrom] = useState('')
  const [createdTo, setCreatedTo] = useState('')
  const [paidFrom, setPaidFrom] = useState('')
  const [paidTo, setPaidTo] = useState('')
  const [page, setPage] = useState(1)

  const orders = useQuery({
    queryKey: ['admin', 'orders', status, orderNo, userQ, packId, createdFrom, createdTo, paidFrom, paidTo, page],
    queryFn: () =>
      listOrders({
        status,
        order_no: orderNo,
        user: userQ,
        pack_id: packId,
        created_from: createdFrom,
        created_to: createdTo,
        paid_from: paidFrom,
        paid_to: paidTo,
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
      }),
    placeholderData: keepPreviousData,
  })
  const total = orders.data?.total ?? 0

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-[20px] text-ink [font-family:var(--font-display)]">订单</h1>

      <div className="overflow-hidden rounded-md border border-hairline">
        <table className="w-full text-[13px]">
          <thead className="bg-wash/60 text-left font-ui text-muted-ink">
            <tr>
              <th className="px-3 py-2">
                <div className="flex items-center gap-1">
                  <span>订单号</span>
                  <FilterMenu active={orderNo !== ''} label="订单号" className="w-64">
                    <SearchFilter
                      value={orderNo}
                      placeholder="搜索订单号…"
                      onChange={(v) => {
                        setOrderNo(v)
                        setPage(1)
                      }}
                    />
                  </FilterMenu>
                </div>
              </th>
              <th className="px-3 py-2">
                <div className="flex items-center gap-1">
                  <span>用户</span>
                  <FilterMenu active={userQ !== ''} label="用户" className="w-64">
                    <SearchFilter
                      value={userQ}
                      placeholder="搜索用户名 / ID…"
                      onChange={(v) => {
                        setUserQ(v)
                        setPage(1)
                      }}
                    />
                  </FilterMenu>
                </div>
              </th>
              <th className="px-3 py-2">
                <div className="flex items-center gap-1">
                  <span>积分包</span>
                  <FilterMenu active={packId !== ''} label="积分包" className="w-40">
                    <OptionList
                      value={packId}
                      options={PACK_OPTIONS}
                      onPick={(v) => {
                        setPackId(v)
                        setPage(1)
                      }}
                    />
                  </FilterMenu>
                </div>
              </th>
              <th className="px-3 py-2">金额</th>
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
              <th className="px-3 py-2">
                <div className="flex items-center gap-1">
                  <span>创建时间</span>
                  <FilterMenu active={!!(createdFrom || createdTo)} label="创建时间">
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
                  <span>支付时间</span>
                  <FilterMenu active={!!(paidFrom || paidTo)} label="支付时间">
                    <DateRangeFilter
                      from={paidFrom}
                      to={paidTo}
                      onChange={(f, t) => {
                        setPaidFrom(f)
                        setPaidTo(t)
                        setPage(1)
                      }}
                    />
                  </FilterMenu>
                </div>
              </th>
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
                <td className="px-3 py-2 text-muted-ink">
                  {o.pack_id}
                  <span className="ml-1 font-ui text-[11px] tabular-nums text-quiet">{o.credits} 积分 · {o.channel}</span>
                </td>
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
