import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { toast } from 'sonner'
import { getCreditLedger } from '@/api/credits'
import { createOrder, getPacks, getPaymentConfig } from '@/api/payment'
import { PageHeader } from '@/components/PageHeader'
import { PayQrDialog } from '@/components/PayQrDialog'
import { StatTile } from '@/components/StatTile'
import { useCredits } from '@/hooks/useCredits'
import { formatYuan } from '@/lib/money'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import type { CreditLedgerItem, PayOrder } from '@/types/payment'

const KIND_LABEL: Record<string, string> = {
  signup_bonus: '注册赠送',
  daily_grant: '每日赠送',
  purchase: '充值',
  spend: '消费',
  refund: '退回',
  admin_adjust: '管理员调整',
  migrate_membership: '会员折算',
}

function fmtTime(iso: string): string {
  const d = new Date(iso)
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const mi = String(d.getMinutes()).padStart(2, '0')
  return `${mm}-${dd} ${hh}:${mi}`
}

/**
 * 积分页（原会员页，2026-08 纯积分制）：余额三格 + 积分包三张 .tile + 价目表 + 流水。
 * 购买流程沿用 PayQrDialog（mock 扫码弹窗 / 真实沙盒网页收银台），支付成功即到账。
 */
export function CreditsPage() {
  const [activeOrder, setActiveOrder] = useState<PayOrder | null>(null)
  const { account, priceTable, isLoading: creditsLoading } = useCredits()

  const packsQuery = useQuery({ queryKey: ['payPacks'], queryFn: getPacks, staleTime: 10 * 60_000 })
  const configQuery = useQuery({ queryKey: ['payConfig'], queryFn: getPaymentConfig, staleTime: 10 * 60_000 })
  const ledgerQuery = useQuery({ queryKey: ['credits', 'ledger'], queryFn: () => getCreditLedger(30, 0) })

  // mock 模式走扫码弹窗(带模拟支付按钮);真实沙盒走网页收银台(无需沙箱 App)
  const channel = configQuery.data?.mock_pay === false ? 'web' : 'qr'

  const orderMutation = useMutation({
    mutationFn: (packId: string) => createOrder(packId, channel),
    onSuccess: (order) => {
      if (order.pay_url) window.open(order.pay_url, '_blank')
      setActiveOrder(order)
    },
    onError: (err) => toast.error(err.message || '下单失败，请稍后重试'),
  })

  return (
    <div className="flex max-w-[56rem] flex-col gap-10">
      <PageHeader
        title="积分"
        intro="出卷、讲解、批改和学习助手按次扣积分；做题、判分、错题本、掌握度、学情报告、背单词免费。每天赠送一笔当日有效的积分，用完可随时充值。"
      />

      {/* 余额 */}
      {creditsLoading || !account ? (
        <div className="grid gap-3 sm:grid-cols-3">
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
        </div>
      ) : (
        <section className="flex flex-col gap-3">
          <div className="grid gap-3 sm:grid-cols-3">
            <StatTile label="可用积分" value={account.total} />
            <StatTile label="今日赠送剩余" value={account.daily_balance} unit={`/ ${account.daily_grant}`} />
            <StatTile label="累计消费" value={account.spent_total} />
          </div>
          <p className="text-[12.5px] text-quiet">
            可用积分 = 余额 {account.balance}（充值 / 赠送，不过期）+ 今日赠送 {account.daily_balance}（当日有效，次日重置为 {account.daily_grant}）。扣费先用今日赠送，再用余额。
          </p>
        </section>
      )}

      {/* 积分包 */}
      <section className="flex flex-col gap-4">
        <h2 className="font-heading text-[17px] font-bold text-ink">充值</h2>
        {packsQuery.isLoading ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <Skeleton className="h-44" />
            <Skeleton className="h-44" />
            <Skeleton className="h-44" />
          </div>
        ) : packsQuery.isError ? (
          <div className="flex flex-col items-start gap-3">
            <p className="text-[13.5px] text-muted-ink">积分包加载失败，请稍后重试</p>
            <Button variant="outline" size="sm" onClick={() => packsQuery.refetch()}>
              重试
            </Button>
          </div>
        ) : (
          <div className="tile-grid" style={{ ['--tile-cols' as string]: '3' }}>
            {packsQuery.data?.map((pack, i) => {
              const tone = i === 0 ? 'tile--listening' : i === 1 ? 'tile--reading' : 'tile--accent'
              const perYuan = Math.round(pack.credits / (pack.amount_cents / 100))
              return (
                <div key={pack.id} className={cn('tile', tone)}>
                  <span className="tile-idx">{pack.name}</span>
                  <span className="flex items-baseline gap-2">
                    <span className="font-ui text-[28px] font-bold leading-none tabular-nums text-ink">
                      {pack.credits.toLocaleString()}
                    </span>
                    <span className="font-ui text-[13px] text-quiet">积分</span>
                  </span>
                  <span className="tile-desc">
                    {formatYuan(pack.amount_cents)} · 约 {perYuan} 积分 / 元
                  </span>
                  <span className="tile-desc">{pack.description}</span>
                  <div className="mt-2">
                    <Button size="sm" onClick={() => orderMutation.mutate(pack.id)} disabled={orderMutation.isPending}>
                      {formatYuan(pack.amount_cents)} 购买
                    </Button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
        <p className="text-[12px] text-quiet">
          {configQuery.data?.mock_pay
            ? '当前为离线模拟支付模式，不会产生真实扣款。'
            : '本页为支付宝沙盒环境的模拟支付，不会产生真实扣款。'}
        </p>
      </section>

      {/* 价目 */}
      <section className="flex flex-col gap-4">
        <h2 className="font-heading text-[17px] font-bold text-ink">价目</h2>
        {priceTable ? (
          <table className="w-full text-[13.5px]">
            <thead>
              <tr className="border-b border-ink-20 text-left">
                <th className="kicker py-2.5 pr-4">动作</th>
                <th className="kicker w-36 py-2.5 text-right">积分</th>
                <th className="kicker py-2.5 pl-6">说明</th>
              </tr>
            </thead>
            <tbody>
              {priceTable.items.map((p) => (
                <tr key={p.action} className="border-b border-hairline transition-colors hover:bg-tint">
                  <td className="py-2.5 pr-4 text-ink">{p.label}</td>
                  <td className="py-2.5 text-right font-ui tabular-nums text-ink">
                    {p.per_unit > 0 ? `${p.base} + ${p.per_unit} / ${p.unit}` : `${p.base} / 次`}
                  </td>
                  <td className="py-2.5 pl-6 text-quiet">{p.note}</td>
                </tr>
              ))}
              <tr className="border-b border-hairline">
                <td className="py-2.5 pr-4 text-ink">做题、判分、错题本、掌握度、学情报告、打印、背单词</td>
                <td className="py-2.5 text-right font-ui text-success">免费</td>
                <td className="py-2.5 pl-6 text-quiet">不调用 AI</td>
              </tr>
            </tbody>
          </table>
        ) : (
          <Skeleton className="h-40" />
        )}
        {priceTable && (
          <p className="text-[12px] text-quiet">
            注册赠送 {priceTable.signup_bonus} 积分；每天赠送 {priceTable.daily_grant} 积分（当日有效）。出卷失败会原路退回。
          </p>
        )}
      </section>

      {/* 流水 */}
      <section className="flex flex-col gap-4">
        <h2 className="font-heading text-[17px] font-bold text-ink">流水</h2>
        {ledgerQuery.isLoading ? (
          <Skeleton className="h-32" />
        ) : (ledgerQuery.data?.items.length ?? 0) === 0 ? (
          <p className="text-[13.5px] text-muted-ink">还没有流水</p>
        ) : (
          <ul className="flex flex-col">
            {ledgerQuery.data?.items.map((row: CreditLedgerItem) => (
              <li
                key={row.id}
                className="grid grid-cols-[88px_minmax(0,1fr)_auto] items-baseline gap-x-4 border-b border-hairline py-2.5 text-[13.5px]"
              >
                <span className="font-ui text-[12.5px] tabular-nums text-quiet">{fmtTime(row.created_at)}</span>
                <span className="min-w-0 truncate text-ink">
                  {KIND_LABEL[row.kind] ?? row.kind}
                  {row.note ? <span className="text-quiet"> · {row.note}</span> : null}
                  {row.bucket === 'daily' && row.kind === 'spend' ? (
                    <span className="text-quiet">（今日赠送）</span>
                  ) : null}
                </span>
                <span
                  className={cn(
                    'font-ui tabular-nums',
                    row.delta > 0 ? 'text-success' : row.delta < 0 ? 'text-ink' : 'text-quiet',
                  )}
                >
                  {row.delta > 0 ? `+${row.delta}` : row.delta}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <PayQrDialog
        order={activeOrder}
        onClose={() => setActiveOrder(null)}
        onReorder={(packId) => orderMutation.mutate(packId)}
        reorderPending={orderMutation.isPending}
      />
    </div>
  )
}
