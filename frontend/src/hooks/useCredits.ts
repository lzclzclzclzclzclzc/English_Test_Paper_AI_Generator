import { useQuery } from '@tanstack/react-query'
import { getCreditPrices, getMyCredits } from '@/api/credits'
import { queryClient } from '@/lib/queryClient'
import type { CreditAction, CreditPrice } from '@/types/payment'

export const CREDITS_QUERY_KEY = ['credits', 'me'] as const
export const PRICES_QUERY_KEY = ['credits', 'prices'] as const

/** 任何付费动作成功 / 充值成功后调用：余额重取。 */
export function invalidateCredits() {
  void queryClient.invalidateQueries({ queryKey: CREDITS_QUERY_KEY })
}

/** 按价目表算价：base + per_unit × units。表未加载时返回 null（别显示 0）。 */
export function priceOf(items: CreditPrice[] | undefined, action: CreditAction | string, units = 0): number | null {
  const p = items?.find((i) => i.action === action)
  if (!p) return null
  return p.base + p.per_unit * Math.max(0, units)
}

/**
 * 积分账户 + 价目表（全站共享缓存；['credits','me'] 在出卷/讲解/批改/聊天成功与充值后失效重取）。
 * 价目表来自后端 GET /api/credits/prices —— 前端不硬编码价格。
 */
export function useCredits() {
  const account = useQuery({ queryKey: CREDITS_QUERY_KEY, queryFn: getMyCredits, staleTime: 15_000 })
  const prices = useQuery({ queryKey: PRICES_QUERY_KEY, queryFn: getCreditPrices, staleTime: 10 * 60_000 })
  const total = account.data?.total ?? null
  return {
    account: account.data ?? null,
    /** 当前可用（balance + daily），未加载为 null */
    total,
    balance: account.data?.balance ?? null,
    daily: account.data?.daily_balance ?? null,
    dailyGrant: account.data?.daily_grant ?? prices.data?.daily_grant ?? null,
    priceTable: prices.data ?? null,
    isLoading: account.isLoading || prices.isLoading,
    price: (action: CreditAction | string, units = 0) => priceOf(prices.data?.items, action, units),
    /** 余额已知且小于 cost → false；余额未知（加载中/失败）→ true（交给服务端 402 兜底） */
    canAfford: (cost: number | null) => (total === null || cost === null ? true : total >= cost),
    refresh: invalidateCredits,
  }
}
