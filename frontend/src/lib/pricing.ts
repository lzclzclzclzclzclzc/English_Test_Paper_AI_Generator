/**
 * 积分包 / 免费额度 / 价目的静态镜像 —— 只给营销首页的匿名展示用
 * （不能发认证请求）。权威在后端：
 *   - 积分包：backend/services/payment/packs.py（积分页的购买路径走 getPacks() 实时数据）
 *   - 价目表：backend/services/credits/pricing.py（站内一律走 GET /api/credits/prices）
 *   - 赠送：shared/config.py CreditsConfig
 * 改价必须同步这里。
 */
export interface PricingPack {
  id: string
  name: string
  credits: number
  amountCents: number
  /** 折算行（「比入门包多送 20%」），空缺不显示 */
  note?: string
  recommended?: boolean
}

export const PRICING_PACKS: readonly PricingPack[] = [
  { id: 'starter', name: '入门包', credits: 1000, amountCents: 990 },
  { id: 'standard', name: '标准包', credits: 3000, amountCents: 2500, note: '比入门包多送 20%' },
  { id: 'annual', name: '畅练包', credits: 12000, amountCents: 8800, note: '比入门包多送 35%', recommended: true },
]

export const SIGNUP_BONUS = 300
export const DAILY_GRANT = 30

/** 免费档一句话(营销首页定价区第一列) */
export const FREE_TIER_SUMMARY = `注册送 ${SIGNUP_BONUS} 积分，每天再送 ${DAILY_GRANT} 积分`

export interface PriceRow {
  feature: string
  cost: string
}

/** 价目（营销首页用的静态镜像；站内用 useCredits().priceTable） */
export const PRICE_ROWS: readonly PriceRow[] = [
  { feature: '出卷 · 真题原样', cost: '5 + 1 / 题' },
  { feature: '出卷 · AI 改编', cost: '5 + 3 / 题' },
  { feature: '出卷 · 全新出题（含复习卷 / 巩固卷 / 主题出卷）', cost: '5 + 4 / 题' },
  { feature: '一句话重新出卷', cost: '5 + 4 / 题' },
  { feature: 'AI 单题讲解', cost: '5 / 题' },
  { feature: '作文批改', cost: '20 / 篇' },
  { feature: '学习助手', cost: '2 / 条消息' },
  { feature: '做题、判分、错题本、掌握度、学情报告、打印、背单词', cost: '免费' },
]
