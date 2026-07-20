import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { toast } from 'sonner'
import { BadgeCheck } from 'lucide-react'
import { createOrder, getMembership, getPayHealth, getPlans } from '@/api/payment'
import { PayQrDialog } from '@/components/PayQrDialog'
import { formatYuan } from '@/lib/money'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import type { PayOrder } from '@/types/payment'

/** 权益对比：与实际前端门槛一一对应（quota.ts / GenerateForm / PaperPage）。 */
const BENEFITS = [
  { feature: '按描述生成新卷', free: '每天 3 次', member: '不限次数' },
  { feature: '错题巩固 / 综合复习', free: '—', member: '✓' },
  { feature: 'AI 单题解析', free: '每天 2 次', member: '不限次数' },
  { feature: '一句话重新出卷', free: '—', member: '✓' },
  { feature: '做题与判分', free: '✓', member: '✓' },
] as const

function formatDate(iso: string): string {
  const d = new Date(iso)
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${mm}-${dd}`
}

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
    <div className="mx-auto flex max-w-[760px] flex-col gap-6 px-6 pt-12">
      <div className="flex flex-col gap-1">
        <h1 className="font-serif text-2xl font-bold text-foreground">会员</h1>
        <p className="text-[13.5px] text-text-mid">开通会员,解锁不限量组卷与全部功能</p>
      </div>

      {membershipQuery.isLoading ? (
        <Skeleton className="h-12 w-full" />
      ) : membership?.active && membership.expires_at ? (
        <div className="flex items-center gap-2 rounded-md border border-ink/25 bg-[#eef2f7] px-4 py-3">
          <BadgeCheck className="size-4 text-ink" />
          <span className="text-[13.5px] font-medium text-ink">
            会员有效期至 {formatDate(membership.expires_at)}
          </span>
        </div>
      ) : (
        <div className="rounded-md border border-line bg-sheet px-4 py-3 text-[13.5px] text-text-mid">
          {membership?.expires_at
            ? `会员已于 ${formatDate(membership.expires_at)} 到期,续费后从今天起重新计算`
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
        <div className="flex flex-col items-center gap-3 py-16">
          <p className="text-[13.5px] text-muted-foreground">套餐加载失败,请确认支付服务已启动</p>
          <Button variant="outline" size="sm" onClick={() => plansQuery.refetch()}>
            重试
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {plansQuery.data?.map((plan) => (
            <Card key={plan.id} className="rounded-md">
              <CardContent className="flex flex-col items-center gap-3 pt-2 text-center">
                <span className="font-serif text-[15px] font-bold text-foreground">
                  {plan.name}
                </span>
                <span className="text-2xl font-bold text-ink">
                  {formatYuan(plan.amount_cents)}
                </span>
                <span className="text-[12.5px] text-text-mid">{plan.description}</span>
                <Button
                  className="w-full"
                  size="sm"
                  onClick={() => orderMutation.mutate(plan.id)}
                  disabled={orderMutation.isPending}
                >
                  {membership?.active ? '续费' : '立即开通'}
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <div>
        <h2 className="mb-3 font-serif text-[15px] font-bold text-foreground">权益对比</h2>
        <div className="overflow-hidden rounded-md border border-line bg-sheet">
          <table className="w-full text-[13px]">
            <thead>
              <tr className="border-b border-line bg-ink-wash/60 text-text-mid">
                <th className="px-4 py-2.5 text-left font-normal">功能</th>
                <th className="w-28 px-4 py-2.5 text-center font-normal">免费</th>
                <th className="w-28 px-4 py-2.5 text-center font-bold text-ink">会员</th>
              </tr>
            </thead>
            <tbody>
              {BENEFITS.map((b) => (
                <tr key={b.feature} className="border-b border-line last:border-0">
                  <td className="px-4 py-2.5 text-foreground">{b.feature}</td>
                  <td className="px-4 py-2.5 text-center text-text-mid">{b.free}</td>
                  <td className="px-4 py-2.5 text-center font-medium text-ink">{b.member}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <p className="text-[12px] text-muted-foreground">
        {healthQuery.data?.mock_pay
          ? '当前为离线模拟支付模式,不会产生真实扣款。'
          : '本页为支付宝沙盒环境的模拟支付,不会产生真实扣款。'}
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
