/**
 * 积分 / 支付契约类型。权威来源：backend/schemas.py（credits / payment 段）。
 * 2026-08 起支付服务已并入主后端（/api/payment、/api/credits），不再有独立 /payapi。
 */

export type OrderStatus = 'CREATED' | 'PAID' | 'EXPIRED' | 'CLOSED'

/** qr = 当面付扫码(需沙箱版支付宝 App);web = 电脑网站支付(桌面浏览器收银台) */
export type PayChannel = 'qr' | 'web'

/** 积分包（GET /api/payment/packs） */
export interface Pack {
  id: string
  name: string
  credits: number
  amount_cents: number
  description: string
}

export interface PaymentConfig {
  mock_pay: boolean
}

export interface PayOrder {
  out_trade_no: string
  pack_id: string
  amount_cents: number
  credits: number
  status: OrderStatus
  channel: PayChannel
  qr_code: string | null
  pay_url: string | null
  created_at: string
  expires_at: string
  paid_at: string | null
}

/** GET /api/credits/me */
export interface CreditAccount {
  /** 付费 / 赠送余额（不过期） */
  balance: number
  /** 今日赠送剩余（当日有效） */
  daily_balance: number
  /** 每日赠送额度（配置） */
  daily_grant: number
  /** balance + daily_balance，即当前可用 */
  total: number
  spent_total: number
}

export type CreditAction =
  | 'generate_original'
  | 'generate_light'
  | 'generate_fresh'
  | 'revise_paper'
  | 'solution'
  | 'writing_grade'
  | 'vocab_example'
  | 'agent_message'

export interface CreditPrice {
  action: CreditAction | string
  label: string
  base: number
  per_unit: number
  unit: string
  note: string
}

export interface CreditPriceTable {
  items: CreditPrice[]
  signup_bonus: number
  daily_grant: number
}

export type LedgerKind =
  | 'signup_bonus'
  | 'daily_grant'
  | 'purchase'
  | 'spend'
  | 'refund'
  | 'admin_adjust'
  | 'migrate_membership'

export interface CreditLedgerItem {
  id: number
  delta: number
  bucket: 'daily' | 'balance'
  balance_after: number
  kind: LedgerKind | string
  action: string | null
  ref_type: string | null
  ref_id: string | null
  note: string | null
  created_at: string
}

export interface CreditLedgerList {
  items: CreditLedgerItem[]
  total: number
}

/** 付费动作响应里附带的本次扣费信息 */
export interface CreditChargeInfo {
  cost: number
  balance_after: number
  daily_after: number
}

/** 402 credits.insufficient 的 detail */
export interface InsufficientCreditsDetail {
  required: number
  available: number
  action?: string
}
