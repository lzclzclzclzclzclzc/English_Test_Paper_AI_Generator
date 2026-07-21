import { Outlet } from 'react-router-dom'
import { AppNav } from '@/components/AppNav'
import { useKnowledgePoints } from '@/hooks/useKnowledgePoints'

/** 受保护页面的共享布局：导航 + 内容区。各页面自管内容最大宽度（Spec F § 6）。 */
export function AppLayout() {
  // 登录后拉取知识点目录，填充 id→中文名映射（全站 prettifyKp 生效）
  useKnowledgePoints()

  return (
    <div className="min-h-svh bg-background">
      <AppNav />
      <main className="pb-16">
        <Outlet />
      </main>
    </div>
  )
}
