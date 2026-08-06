import { Navigate, useParams } from 'react-router-dom'
import { DrillPageTemplate } from '@/components/drill/DrillPageTemplate'
import { drillBySlug } from '@/lib/drillConfig'
import { PATHS } from '@/lib/paths'

/**
 * 题型专项页路由壳：/practice/:slug → DrillConfig → 模板。
 * key 按 slug 重置模板内部状态（题量/考点不跨题型残留）。
 */
export function DrillPage() {
  const { slug } = useParams<{ slug: string }>()
  const config = slug ? drillBySlug(slug) : undefined
  if (!config) return <Navigate to={PATHS.home} replace />
  return <DrillPageTemplate key={config.slug} config={config} />
}
