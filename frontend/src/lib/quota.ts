/**
 * 免费用户每日配额（第一阶段：纯前端体现，localStorage 按天计数）。
 * 只做产品层面的引导，不是安全边界；真实强制需主后端配合（见会员方案第三阶段）。
 */
export const FREE_GENERATE_PER_DAY = 3
export const FREE_SOLUTION_PER_DAY = 2

export type QuotaFeature = 'generate' | 'solution'

const PREFIX = 'mj.quota.'

function localDay(): string {
  const d = new Date()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${mm}-${dd}`
}

const keyOf = (userId: string, feature: QuotaFeature) =>
  `${PREFIX}${userId}.${feature}.${localDay()}`

function used(userId: string, feature: QuotaFeature): number {
  const raw = localStorage.getItem(keyOf(userId, feature))
  const n = raw === null ? 0 : Number.parseInt(raw, 10)
  return Number.isFinite(n) && n > 0 ? n : 0
}

export function quotaRemaining(userId: string, feature: QuotaFeature, limit: number): number {
  return Math.max(0, limit - used(userId, feature))
}

/** 非会员的免费出卷提示文案;会员返回 null。一句话出卷与各专项面板共用。 */
export function generateQuotaNotice(locked: boolean, remaining: number): string | null {
  if (!locked) return null
  return remaining > 0
    ? `今日免费出卷剩 ${remaining} 次，开通会员不限次数`
    : `今日 ${FREE_GENERATE_PER_DAY} 次免费出卷已用完，开通会员后不限次数`
}

/** 计一次用量，并顺手清掉往日的计数键。 */
export function consumeQuota(userId: string, feature: QuotaFeature): void {
  localStorage.setItem(keyOf(userId, feature), String(used(userId, feature) + 1))
  const day = localDay()
  for (let i = localStorage.length - 1; i >= 0; i--) {
    const k = localStorage.key(i)
    if (k?.startsWith(PREFIX) && !k.endsWith(day)) localStorage.removeItem(k)
  }
}
