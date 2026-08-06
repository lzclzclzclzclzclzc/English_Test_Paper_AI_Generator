import { Navigate, useParams } from 'react-router-dom'
import { PageHeader } from '@/components/PageHeader'
import { PATHS } from '@/lib/paths'

/** 题型专项页路由壳。占位版:PR3 接入 drillConfig + DrillPageTemplate。 */
export function DrillPage() {
  const { slug } = useParams<{ slug: string }>()
  if (!slug) return <Navigate to={PATHS.home} replace />
  return (
    <div className="max-w-[52rem]">
      <PageHeader title="题型专项" intro={slug} />
    </div>
  )
}
