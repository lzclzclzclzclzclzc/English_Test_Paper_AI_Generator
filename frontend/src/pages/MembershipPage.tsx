import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { toast } from 'sonner'
import { createOrder, getMembership, getPayHealth, getPlans } from '@/api/payment'
import { PageHeader } from '@/components/PageHeader'
import { PayQrDialog } from '@/components/PayQrDialog'
import { formatYuan } from '@/lib/money'
import { BENEFITS } from '@/lib/pricing'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import type { PayOrder } from '@/types/payment'

function formatDate(iso: string): string {
  const d = new Date(iso)
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${mm}-${dd}`
}

/** 会员（喫茶去外观）：无卡片，套餐为细线分栏，价格用赤陶数字。 */
export function MembershipPage() {
  const [activeOrder, setActiveOrder] = useState<PayOrder | null>(null)

  const membershipQuery = useQuery({ queryKey: ['payMembership'], queryFn: getMembership })
  const plansQuery = useQuery({ queryKey: ['payPlans'], queryFn: getPlans })
  const healthQuery = useQuery({ queryKey: ['payHealth'], queryFn: getPayHealth })

  // mock 模式走扫码弹窗(带模拟支付按钮);真实沙盒走网页收银台(无需沙箱 App)
  const channel = healthQuery.data?.mock_pay === false ? 'web' : 'qr'

  const orderMutation = useMutation({
    mutationFn: (planId: string) => createOrder(planId, channel),
    onSuccess: (order) => {
      if (order.pay_url) window.open(order.pay_url, '_blank')
      setActiveOrder(order)
    },
    onError: (err) => toast.error(err.message || '下单失败,请稍后重试'),
  })

  const membership = membershipQuery.data

  return (
    <div className="flex max-w-[52rem] flex-col gap-10">
      <PageHeader title="会员" intro="开通会员，解锁不限量组卷与全部功能。" />

      {membershipQuery.isLoading ? (
        <Skeleton className="h-10 w-full" />
      ) : membership?.active && membership.expires_at ? (
        <div className="border-t border-accent pt-2.5 text-[13.5px] text-ink">
          会员有效期至 <b>{formatDate(membership.expires_at)}</b>
        </div>
      ) : (
        <div className="border-t border-hairline pt-2.5 text-[13.5px] text-muted-ink">
          {membership?.expires_at
            ? `会员已于 ${formatDate(membership.expires_at)} 到期，续费后从今天起重新计算`
            : '尚未开通会员'}
        </div>
      )}

      {plansQuery.isLoading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Skeleton className="h-44" />
          <Skeleton className="h-44" />
          <Skeleton className="h-44" />
        </div>
      ) : plansQuery.isError ? (
        <div className="flex flex-col items-start gap-3">
          <p className="text-[13.5px] text-muted-ink">套餐加载失败，请确认支付服务已启动</p>
          <Button variant="outline" size="sm" onClick={() => plansQuery.refetch()}>
            重试
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-3 divide-x divide-ink-10 border-y border-hairline max-sm:grid-cols-1 max-sm:divide-x-0 max-sm:divide-y max-sm:divide-ink-10">
          {plansQuery.data?.map((plan) => (
            <div key={plan.id} className="flex flex-col gap-3 px-8 py-7 first:pl-2 last:pr-2 max-sm:px-2">
              <span className="text-[15px] text-ink">{plan.name}</span>
              <span className="font-ui text-[28px] font-[650] leading-none tabular-nums text-accent">
                {formatYuan(plan.amount_cents)}
              </span>
              <span className="text-[12.5px] leading-relaxed text-quiet">{plan.description}</span>
              <div className="mt-auto pt-2">
                <Button
                  size="sm"
                  onClick={() => orderMutation.mutate(plan.id)}
                  disabled={orderMutation.isPending}
                >
                  {membership?.active ? '续费' : '立即开通'}
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      <div>
        <h2 className="mb-4 text-[19px] text-ink">权益对比</h2>
        <table className="w-full text-[13.5px]">
          <thead>
            <tr className="border-b border-ink-20 text-left">
              <th className="py-2.5 pr-4 font-ui text-[11px] font-bold tracking-[0.1em] text-quiet">
                功能
              </th>
              <th className="w-28 py-2.5 text-center font-ui text-[11px] font-bold tracking-[0.1em] text-quiet">
                免费
              </th>
              <th className="w-28 py-2.5 text-center font-ui text-[11px] font-bold tracking-[0.1em] text-accent">
                会员
              </th>
            </tr>
          </thead>
          <tbody>
            {BENEFITS.map((b) => (
              <tr key={b.feature} className="border-b border-hairline transition-colors hover:bg-tint">
                <td className="py-2.5 pr-4 text-ink">{b.feature}</td>
                <td className="py-2.5 text-center text-muted-ink">{b.free}</td>
                <td className="py-2.5 text-center text-ink">{b.member}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-[12px] text-quiet">
        {healthQuery.data?.mock_pay
          ? '当前为离线模拟支付模式，不会产生真实扣款。'
          : '本页为支付宝沙盒环境的模拟支付，不会产生真实扣款。'}
      </p>

      <PayQrDialog
        order={activeOrder}
        onClose={() => setActiveOrder(null)}
        onReorder={(planId) => orderMutation.mutate(planId)}
        reorderPending={orderMutation.isPending}
      />
    </div>
  )
}
