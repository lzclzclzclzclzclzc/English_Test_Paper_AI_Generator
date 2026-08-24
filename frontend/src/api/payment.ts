import { apiFetch } from '@/api/client'
import type { Pack, PayChannel, PaymentConfig, PayOrder } from '@/types/payment'

export const getPaymentConfig = () => apiFetch<PaymentConfig>('/payment/config')

export const getPacks = () => apiFetch<Pack[]>('/payment/packs')

export const createOrder = (pack_id: string, channel: PayChannel = 'qr') =>
  apiFetch<PayOrder>('/payment/orders', { method: 'POST', body: JSON.stringify({ pack_id, channel }) })

export const listMyOrders = (limit = 20) => apiFetch<PayOrder[]>(`/payment/orders?limit=${limit}`)

/** 轮询端点：服务端会先做惰性过期检查，再向支付宝查单同步状态。 */
export const getOrder = (outTradeNo: string) => apiFetch<PayOrder>(`/payment/orders/${outTradeNo}`)

export const cancelOrder = (outTradeNo: string) =>
  apiFetch<PayOrder>(`/payment/orders/${outTradeNo}/cancel`, { method: 'POST' })

/** 仅后端 PAYMENT_MOCK=true 时存在；真实沙盒模式下该路由不注册（404）。 */
export const simulatePaid = (outTradeNo: string) =>
  apiFetch<PayOrder>(`/payment/dev/simulate-paid/${outTradeNo}`, { method: 'POST' })
