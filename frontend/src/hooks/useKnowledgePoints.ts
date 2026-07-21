import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { listKnowledgePoints } from '@/api/knowledgePoints'
import { registerKpNames } from '@/lib/kp'

/**
 * 拉取知识点目录并注册 id→中文名映射（供 prettifyKp 用）。
 * 缓存长效——目录基本不变。登录后在共享布局里调用一次即可全站生效。
 */
export function useKnowledgePoints() {
  const query = useQuery({
    queryKey: ['knowledge-points'],
    queryFn: listKnowledgePoints,
    staleTime: Infinity,
    retry: false,
  })

  useEffect(() => {
    if (query.data) registerKpNames(query.data)
  }, [query.data])

  return query
}
