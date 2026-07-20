import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query'
import { ApiError } from '@/api/client'

declare global {
  interface Window {
    /** App.tsx 的 NavigateBridge 挂载时赋值，保证全局 401 跳转走 React Router history。 */
    __appNavigate?: (to: string) => void
  }
}

/** 全局 401：清用户缓存 + 跳登录（Spec D § 6.4）。其余错误交由调用方处理。 */
function handleGlobalError(error: unknown) {
  if (error instanceof ApiError && error.status === 401) {
    queryClient.setQueryData(['auth', 'me'], null)
    if (window.location.pathname !== '/login') {
      window.__appNavigate?.('/login')
    }
  }
}

/** 4xx 不重试（都是确定性失败），5xx/网络错误最多重试 2 次。 */
const retry = (failureCount: number, error: unknown) =>
  !(error instanceof ApiError && error.status < 500) && failureCount < 2

export const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: handleGlobalError }),
  mutationCache: new MutationCache({ onError: handleGlobalError }),
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry,
    },
    mutations: {
      retry: false,
    },
  },
})
