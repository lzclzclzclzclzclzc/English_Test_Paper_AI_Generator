import { useQuery } from '@tanstack/react-query'
import { getMembership } from '@/api/payment'

/**
 * 会员状态（与会员页、支付弹窗共享 ['payMembership'] 缓存，支付成功即失效重取）。
 *
 * locked 才代表「确认是非会员」，只在支付服务明确答复 active=false 时成立：
 * - 加载中不锁，避免会员看到锁标闪烁；
 * - 请求失败（支付服务没跑 / 同源部署没有 /payapi）不锁——视为会员体系未启用，
 *   功能全部放行，远程演示不因缺支付服务而锁死错题巩固/综合复习。
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
    locked: query.isSuccess && !isMember,
    expiresAt: query.data?.expires_at ?? null,
  }
}
