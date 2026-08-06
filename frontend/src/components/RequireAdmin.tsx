import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { Skeleton } from '@/components/ui/skeleton'
import { useAuth } from '@/hooks/useAuth'
import { adminGuardState } from '@/components/requireAdmin.logic'
import { PATHS } from '@/lib/paths'

/** 管理员路由守卫：加载中显示骨架；非管理员重定向首页。
 *  真正的鉴权由后端 require_admin 兜底，这里只控制可见性。 */
export function RequireAdmin({ children }: { children: ReactNode }) {
  const { data: user } = useAuth()
  const state = adminGuardState(user)
  if (state === 'loading') {
    return (
      <div className="mx-auto flex max-w-[880px] flex-col gap-4 p-8">
        <Skeleton className="h-10 w-1/3" />
        <Skeleton className="h-40 w-full" />
      </div>
    )
  }
  if (state === 'redirect') {
    return <Navigate to={PATHS.home} replace />
  }
  return children
}
