import { useQuery } from '@tanstack/react-query'
import { getMembership } from '@/api/payment'

/**
 * 会员状态（与会员页、支付弹窗共享 ['payMembership'] 缓存，支付成功即失效重取）。
 * locked 才代表「确认是非会员」：加载中不锁，避免会员看到锁标闪烁；
 * 支付服务不可用时按非会员处理（锁定，但会员页可重试）。
 */
export function useMembership() {
  const query = useQuery({
    queryKey: ['payMembership'],
    queryFn: getMembership,
    retry: false,
    staleTime: 30_000,
  })
  const isMember = query.data?.active === true
  return {
    isMember,
    locked: !query.isLoading && !isMember,
    expiresAt: query.data?.expires_at ?? null,
  }
}
