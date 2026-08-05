import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { shouldRedirectAdmin } from '@/components/redirectIfAdmin.logic'

/** 普通用户页面外壳：管理员访问时重定向到管理后台（admin 不使用普通功能）。 */
export function RedirectIfAdmin({ children }: { children: ReactNode }) {
  const { data: user } = useAuth()
  if (shouldRedirectAdmin(user)) return <Navigate to="/admin" replace />
  return children
}
