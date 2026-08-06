import { Link } from 'react-router-dom'
import { PageHeader } from '@/components/PageHeader'
import { PATHS } from '@/lib/paths'

/** 工作台(登录后首页)。占位版:PR4 替换为完整版。 */
export function DashboardPage() {
  return (
    <div className="max-w-[52rem]">
      <PageHeader
        title="工作台"
        intro="从这里开始今天的练习:去练习中心选题型,或用一句话描述你想要的卷子。"
      />
      <div className="flex flex-col divide-y divide-ink-10 border-y border-hairline">
        <Link to={PATHS.practice} className="flex items-center justify-between py-4 transition-colors hover:bg-tint">
          <span className="text-[15px] text-ink">练习中心</span>
          <span className="text-[13px] text-quiet">按题型专项练习 →</span>
        </Link>
        <Link to={PATHS.generate} className="flex items-center justify-between py-4 transition-colors hover:bg-tint">
          <span className="text-[15px] text-ink">一句话出卷</span>
          <span className="text-[13px] text-quiet">自由描述任意组合 →</span>
        </Link>
      </div>
    </div>
  )
}
