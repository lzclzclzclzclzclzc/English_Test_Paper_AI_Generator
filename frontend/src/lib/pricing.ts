import { FREE_GENERATE_PER_DAY, FREE_SOLUTION_PER_DAY } from '@/lib/quota'

/**
 * 定价与权益的静态单一来源。
 * PRICING_PLANS 静态镜像 payment/app/plans.py 的 PLANS——权威在后端,改价必须同步;
 * 只服务营销首页的匿名展示(不能调 /payapi,也不能发认证请求)。
 * 会员页的购买路径仍走 getPlans() 实时数据,这里的常量绝不用于下单。
 */
export interface PricingPlan {
  id: string
  name: string
  durationDays: number
  amountCents: number
  /** 折算行(「折合 ¥7.3 / 月」),空缺不显示 */
  perMonthNote?: string
  recommended?: boolean
}

export const PRICING_PLANS: readonly PricingPlan[] = [
  { id: 'monthly', name: '月度会员', durationDays: 30, amountCents: 990 },
  {
    id: 'quarterly',
    name: '季度会员',
    durationDays: 90,
    amountCents: 2500,
    perMonthNote: '折合 ¥8.3 / 月',
  },
  {
    id: 'yearly',
    name: '年度会员',
    durationDays: 365,
    amountCents: 8800,
    perMonthNote: '折合 ¥7.3 / 月',
    recommended: true,
  },
]

/** 免费档一句话(营销首页定价区第一列) */
export const FREE_TIER_SUMMARY = `每天 ${FREE_GENERATE_PER_DAY} 次出卷、${FREE_SOLUTION_PER_DAY} 次讲解`

export interface Benefit {
  feature: string
  free: string
  member: string
}

/**
 * 权益对比:营销首页与会员页共用这一份。
 * 与实际前端门槛一一对应(quota.ts / useGeneratePaper / DrillPageTemplate /
 * PaperPage 打印分版 / MasteryPage 学情报告)。
 */
export const BENEFITS: readonly Benefit[] = [
  { feature: '按描述 / 面板生成新卷', free: `每天 ${FREE_GENERATE_PER_DAY} 次`, member: '不限次数' },
  { feature: 'AI 单题讲解', free: `每天 ${FREE_SOLUTION_PER_DAY} 次`, member: '不限次数' },
  { feature: '做题、判分、错题本、掌握度', free: '✓', member: '✓' },
  { feature: '真题原卷（真题档 / 真题检测卷）', free: '—', member: '✓' },
  { feature: '错题巩固 / 弱点复习卷', free: '—', member: '✓' },
  { feature: '一句话重新出卷', free: '—', member: '✓' },
  { feature: '学情报告（可打印给家长）', free: '—', member: '✓' },
  { feature: '试卷打印 · 学生卷', free: '✓', member: '✓' },
  { feature: '试卷打印 · 教师版（含答案）', free: '—', member: '✓' },
]
