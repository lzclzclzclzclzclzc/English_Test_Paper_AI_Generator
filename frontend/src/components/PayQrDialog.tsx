import { useEffect, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { QRCodeSVG } from 'qrcode.react'
import { CheckCircle2, Clock, ExternalLink } from 'lucide-react'
import { cancelOrder, getOrder, simulatePaid } from '@/api/payment'
import { formatYuan } from '@/lib/money'
import { queryClient } from '@/lib/queryClient'
import type { PayOrder } from '@/types/payment'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

/** 距 expires_at 的剩余 mm:ss;每秒重算。 */
function useCountdown(expiresAt: string | undefined): string {
  const [, setTick] = useState(0)
  useEffect(() => {
    const timer = setInterval(() => setTick((t) => t + 1), 1000)
    return () => clearInterval(timer)
  }, [])
  if (!expiresAt) return '--:--'
  const remain = Math.max(0, Math.floor((new Date(expiresAt).getTime() - Date.now()) / 1000))
  const mm = String(Math.floor(remain / 60)).padStart(2, '0')
  const ss = String(remain % 60).padStart(2, '0')
  return `${mm}:${ss}`
}

interface PayQrDialogProps {
  /** 为 null 时弹窗关闭。 */
  order: PayOrder | null
  onClose: () => void
  /** 二维码过期/订单关闭后点「重新下单」。 */
  onReorder: (planId: string) => void
  reorderPending: boolean
}

/**
 * 扫码支付弹窗（现代控件面,不做仿纸)。
 * 状态机:CREATED(展示二维码+倒计时+2s 轮询)→ PAID(成功,1.5s 后自动关)
 * / EXPIRED / CLOSED(可重新下单)。
 */
export function PayQrDialog({ order: initialOrder, onClose, onReorder, reorderPending }: PayQrDialogProps) {
  const outTradeNo = initialOrder?.out_trade_no

  const { data: order } = useQuery({
    queryKey: ['payOrder', outTradeNo],
    queryFn: () => getOrder(outTradeNo!),
    enabled: !!outTradeNo,
    initialData: initialOrder ?? undefined,
    refetchInterval: (query) => (query.state.data?.status === 'CREATED' ? 2000 : false),
  })

  const simulateMutation = useMutation({
    mutationFn: simulatePaid,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['payOrder', outTradeNo] }),
  })

  const status = order?.status
  const countdown = useCountdown(status === 'CREATED' ? order?.expires_at : undefined)

  // 支付成功:刷新会员状态,短暂展示后自动关闭
  useEffect(() => {
    if (status !== 'PAID') return
    queryClient.invalidateQueries({ queryKey: ['payMembership'] })
    const timer = setTimeout(onClose, 1500)
    return () => clearTimeout(timer)
  }, [status, onClose])

  const handleOpenChange = (open: boolean) => {
    if (open) return
    // 扫码单未支付就关弹窗:尽力关单,失败无所谓(服务端还有惰性过期兜底)。
    // web 单不关:用户可能正在另一个标签页的收银台里付款。
    if (order?.status === 'CREATED' && order.channel === 'qr') {
      cancelOrder(order.out_trade_no).catch(() => {})
    }
    onClose()
  }

  const isMock = order?.qr_code?.startsWith('MOCK|') ?? false

  return (
    <Dialog open={!!initialOrder} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-[340px]">
        <DialogHeader>
          <DialogTitle>
            {order?.channel === 'web' ? '支付宝支付' : '扫码支付'}
          </DialogTitle>
          {order && (
            <DialogDescription className="font-ui tabular-nums">
              {formatYuan(order.amount_cents)} · 订单 {order.out_trade_no}
            </DialogDescription>
          )}
        </DialogHeader>

        {order && status === 'CREATED' && order.channel === 'web' && (
          <div className="flex flex-col items-center gap-3 py-6">
            <p className="text-center text-[13.5px] leading-relaxed text-foreground">
              已在新标签页打开支付宝沙盒收银台，
              <br />
              请用沙箱买家账号登录并完成支付
            </p>
            <Button
              size="sm"
              variant="outline"
              onClick={() => order.pay_url && window.open(order.pay_url, '_blank')}
            >
              <ExternalLink className="size-3.5" />
              重新打开收银台
            </Button>
            <p className="flex items-center gap-1.5 font-ui text-[13px] tabular-nums text-muted-ink">
              <Clock className="size-3.5" />
              {countdown} 内有效，支付完成后本页自动刷新
            </p>
          </div>
        )}

        {order && status === 'CREATED' && order.channel === 'qr' && (
          <div className="flex flex-col items-center gap-3 py-2">
            <div className="rounded-md border border-hairline bg-white p-3">
              <QRCodeSVG value={order.qr_code ?? ''} size={200} />
            </div>
            <p className="flex items-center gap-1.5 font-ui text-[13px] tabular-nums text-muted-ink">
              <Clock className="size-3.5" />
              {countdown} 内使用沙箱版支付宝扫码支付
            </p>
            {isMock && (
              <Button
                size="sm"
                variant="outline"
                onClick={() => simulateMutation.mutate(order.out_trade_no)}
                disabled={simulateMutation.isPending}
              >
                模拟支付成功(离线模式)
              </Button>
            )}
          </div>
        )}

        {status === 'PAID' && (
          <div className="flex flex-col items-center gap-2 py-8">
            <CheckCircle2 className="size-10 text-ink" strokeWidth={1.5} />
            <p className="font-ui text-[15px] text-ink">支付成功</p>
            <p className="font-ui text-[13px] text-muted-ink">会员权益已生效</p>
          </div>
        )}

        {(status === 'EXPIRED' || status === 'CLOSED') && order && (
          <div className="flex flex-col items-center gap-3 py-8">
            <p className="font-ui text-[14px] text-foreground">
              {status === 'EXPIRED' ? '二维码已过期' : '订单已关闭'}
            </p>
            <Button size="sm" onClick={() => onReorder(order.plan_id)} disabled={reorderPending}>
              重新下单
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
