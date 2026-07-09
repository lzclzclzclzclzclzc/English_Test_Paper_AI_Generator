import { useQuery } from '@tanstack/react-query'
import { getMe } from '@/api/auth'

/**
 * 当前用户。data 语义：undefined = 加载中未定，null = 未登录，User = 已登录。
 * getMe 内部把 401 转为 null，所以这里 retry: false 且不会因未登录反复请求。
 */
export function useAuth() {
  return useQuery({
    queryKey: ['auth', 'me'],
    queryFn: getMe,
    retry: false,
    staleTime: Infinity,
  })
}
