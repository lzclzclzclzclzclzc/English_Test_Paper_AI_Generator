/**
 * 支付服务契约类型。
 * 权威来源:payment/app/schemas.py(独立支付小服务,非主后端 schemas.py)。
 */

export type OrderStatus = 'CREATED' | 'PAID' | 'EXPIRED' | 'CLOSED'

/** qr = 当面付扫码(需沙箱版支付宝 App);web = 电脑网站支付(桌面浏览器收银台) */
export type PayChannel = 'qr' | 'web'

export interface Plan {
  id: string
  name: string
  duration_days: number
  amount_cents: number
  description: string
}

export interface Membership {
  user_id: string
  expires_at: string | null
  active: boolean
}

export interface PayOrder {
  out_trade_no: string
  plan_id: string
  amount_cents: number
  status: OrderStatus
  channel: PayChannel
  qr_code: string | null
  pay_url: string | null
  created_at: string
  expires_at: string
  paid_at: string | null
}

export interface PayHealth {
  status: string
  mock_pay: boolean
}
