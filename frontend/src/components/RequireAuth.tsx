import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { Skeleton } from '@/components/ui/skeleton'
import { useAuth } from '@/hooks/useAuth'

/**
 * 路由守卫（Spec D § 3.2）：加载中渲染骨架，未登录重定向 /login 并携带来路。
 * 跳转只依赖 useAuth 的缓存状态；全局 401 处理会把 ['auth','me'] 置 null，
 * 本组件感知后自然重定向——自身绝不额外发起请求。
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { data: user, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return (
      <div className="mx-auto flex max-w-[880px] flex-col gap-4 p-8">
        <Skeleton className="h-10 w-1/3" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    )
  }

  if (!user) {
    return (
      <Navigate
        to="/login"
        replace
        state={{ from: location.pathname + location.search }}
      />
    )
  }

  return children
}
