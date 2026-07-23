import { useQuery } from '@tanstack/react-query'
import { getMembership } from '@/api/payment'

/**
 * 会员状态（与会员页、支付弹窗共享 ['payMembership'] 缓存，支付成功即失效重取）。
 * locked 才代表「确认是非会员」：加载中不锁，避免会员看到锁标闪烁；
 * 支付服务不可用时按会员处理（不锁定），避免联调时功能被阻断。
 */
export function useMembership() {
  const query = useQuery({
    queryKey: ['payMembership'],
    queryFn: getMembership,
    retry: false,
    staleTime: 30_000,
  })
  // 支付服务出错时 isError=true，此时默认放行（不锁），仅明确返回 active:false 才锁
  const isMember = query.isError || query.data?.active === true
  return {
    isMember,
    locked: !query.isLoading && !isMember,
    expiresAt: query.data?.expires_at ?? null,
  }
}
