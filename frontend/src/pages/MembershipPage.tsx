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

      <p className="text-[12px] text-muted-foreground">
        本页为支付宝沙盒环境的模拟支付,不会产生真实扣款。
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
