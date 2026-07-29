import { Outlet } from 'react-router-dom'
import { Sidebar } from '@/components/Sidebar'

/** 受保护页面的共享外壳（handoff 第 3 屏）：左侧可折叠导航 + 内容区（左右 56px）。 */
export function AppLayout() {
  return (
    <div className="flex min-h-svh bg-background">
      <Sidebar />
      <main className="min-w-0 flex-1 px-14 pb-20 pt-10 max-md:px-6">
        <Outlet />
      </main>
    </div>
  )
}
