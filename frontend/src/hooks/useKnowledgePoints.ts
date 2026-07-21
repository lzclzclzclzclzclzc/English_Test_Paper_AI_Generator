import { useQuery } from '@tanstack/react-query'
import { listKnowledgePoints } from '@/api/knowledgePoints'
import { registerKpNames } from '@/lib/kp'

/**
 * 拉取知识点目录并注册 id→中文名映射（供 prettifyKp 用）。
 * 缓存长效——目录基本不变。登录后在共享布局里调用一次即可全站生效。
 *
 * 同步注册（render 期间，非 useEffect）：React 先渲染父组件再渲染子组件，
 * 父组件里同步填好映射，子组件本次渲染就能读到中文名——避免"先渲染出英文
 * slug、effect 后填表却不触发重渲染"导致冷加载页面卡在 slug 的问题。
 * registerKpNames 幂等，重复调用无副作用。
 */
export function useKnowledgePoints() {
  const query = useQuery({
    queryKey: ['knowledge-points'],
    queryFn: listKnowledgePoints,
    staleTime: Infinity,
    retry: false,
  })

  if (query.data) registerKpNames(query.data)

  return query
}
