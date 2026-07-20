import { useQuery } from '@tanstack/react-query'
import { getPaper } from '@/api/papers'

/**
 * 单份试卷。Paper 生成后不可变（revise 产生新 paper_id），
 * 所以 staleTime: Infinity——generate/revise 成功后 setQueryData 塞入的缓存
 * 在导航到 /papers/:id 时直接命中，零请求；刷新丢缓存则自动重拉。
 */
export function usePaper(paperId: string) {
  return useQuery({
    queryKey: ['paper', paperId],
    queryFn: () => getPaper(paperId),
    staleTime: Infinity,
  })
}
