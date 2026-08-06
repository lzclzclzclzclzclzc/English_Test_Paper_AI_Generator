import { Navigate } from 'react-router-dom'
import { Skeleton } from '@/components/ui/skeleton'
import { AppLayout } from '@/components/AppLayout'
import { shouldRedirectAdmin } from '@/components/redirectIfAdmin.logic'
import { useAuth } from '@/hooks/useAuth'
import { LandingPage } from '@/pages/LandingPage'
import { DashboardPage } from '@/pages/DashboardPage'
import { PATHS } from '@/lib/paths'

/**
 * `/` 双态入口:未登录 → 营销首页(不挂 AppLayout,除 GET /auth/me 外零请求);
 * 已登录 → 工作台;管理员 → 管理后台。
 * 加载中渲染骨架,避免营销页对已登录用户闪现。
 */
export function HomeGate() {
  const { data: user, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="mx-auto flex max-w-[880px] flex-col gap-4 p-8">
        <Skeleton className="h-10 w-1/3" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    )
  }

  if (!user) return <LandingPage />

  if (shouldRedirectAdmin(user)) return <Navigate to={PATHS.admin} replace />

  return (
    <AppLayout>
      <DashboardPage />
    </AppLayout>
  )
}
