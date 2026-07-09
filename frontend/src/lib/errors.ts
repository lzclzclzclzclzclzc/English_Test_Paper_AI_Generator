import { toast } from 'sonner'
import { ApiError } from '@/api/client'

/**
 * ErrorResponse → 用户可读提示（Spec D § 5.3）。
 * 401 由 queryClient 全局处理（跳登录），这里不重复提示。
 * 表单内错误（invalid_credentials / username_conflict / ai.parser_failed / ai.no_candidate）
 * 由表单自己 setError 展示，调用方不应把它们交给本函数。
 */
export function toastApiError(error: unknown) {
  if (!(error instanceof ApiError)) {
    toast.error('网络异常，请检查连接后重试')
    return
  }
  const { error_code, message, trace_id } = error.payload
  switch (error_code) {
    case 'auth.unauthorized':
      return // 全局 401 已跳登录
    case 'rate.exceeded':
      toast.error('请求过于频繁，请稍后再试')
      return
    case 'resource.not_found':
    case 'request.invalid':
      toast.error(message)
      return
    case 'ai.llm_upstream':
      toast.error('AI 服务暂时不可用，请稍后重试')
      return
    case 'server.internal':
      toast.error(`服务暂时不可用（trace: ${trace_id.slice(0, 8)}）`)
      return
    default:
      // 其余 ai.* 与未知错误码：直接展示后端 message
      toast.error(message)
  }
}
