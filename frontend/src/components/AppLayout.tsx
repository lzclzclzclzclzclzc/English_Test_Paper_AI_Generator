import type { ReactNode } from 'react'
import { Outlet } from 'react-router-dom'
import { Sidebar } from '@/components/Sidebar'
import { useKnowledgePoints } from '@/hooks/useKnowledgePoints'

/**
 * 受保护页面的共享外壳（handoff 第 3 屏）：左侧可折叠导航 + 内容区（左右 56px）。
 * 默认渲染路由 Outlet;HomeGate 等非嵌套场景可直接传 children。
 */
export function AppLayout({ children }: { children?: ReactNode }) {
  // 登录后拉取知识点目录，填充 id→中文名映射（全站 prettifyKp 生效）
  useKnowledgePoints()

  return (
    <div className="flex min-h-svh bg-background">
      <Sidebar />
      <main className="min-w-0 flex-1 px-14 pb-20 pt-10 max-md:px-6">
        {children ?? <Outlet />}
      </main>
    </div>
  )
}
