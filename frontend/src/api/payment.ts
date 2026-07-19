import { payFetch } from '@/api/client'
import type { Membership, PayChannel, PayHealth, PayOrder, Plan } from '@/types/payment'

export const getPayHealth = () => payFetch<PayHealth>('/health')

export const getPlans = () => payFetch<Plan[]>('/plans')

export const getMembership = () => payFetch<Membership>('/membership/me')

export const createOrder = (plan_id: string, channel: PayChannel = 'qr') =>
  payFetch<PayOrder>('/orders', { method: 'POST', body: JSON.stringify({ plan_id, channel }) })

/** 轮询端点：服务端会先做惰性过期检查，再向支付宝查单同步状态。 */
export const getOrder = (outTradeNo: string) => payFetch<PayOrder>(`/orders/${outTradeNo}`)

export const cancelOrder = (outTradeNo: string) =>
  payFetch<PayOrder>(`/orders/${outTradeNo}/cancel`, { method: 'POST' })

/** 仅支付服务 MOCK_PAY=true 时存在；真实沙盒模式下该路由不注册（404）。 */
export const simulatePaid = (outTradeNo: string) =>
  payFetch<PayOrder>(`/dev/simulate-paid/${outTradeNo}`, { method: 'POST' })
