import { useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { generatePaper } from '@/api/papers'
import { ApiError } from '@/api/client'
import { openCreditsDialog } from '@/components/CreditsDialog'
import { useCredits } from '@/hooks/useCredits'
import { toastApiError } from '@/lib/errors'
import { queryClient } from '@/lib/queryClient'
import type { GeneratePaperRequest } from '@/types/api'

/**
 * 生成试卷的共享逻辑（生成页 / 专项 / 自选 / 整卷 / 每日 / 主题 / 错题 / 复习）：
 * 成功后种缓存零请求进卷、失效列表、刷新积分余额、导航到新卷；
 * ai.parser_failed / ai.no_candidate 走 onFormError 表单内提示，其余 toast
 * （402 credits.insufficient 由 toastApiError 转成充值弹窗）。
 *
 * 积分门槛在服务端（Parser 解析出强度 × 题数后扣费）；前端只做两件事：
 *  - `guard(estimatedCost)`：页面能算出确切价格时（专项 / 自选 / 整卷知道强度与题数）
 *    先本地预检，余额明显不够就直接弹充值，省一次请求；算不出（一句话出卷）传 null 放行。
 *  - 成功 / 失败都 invalidate 余额。
 */
export function useGeneratePaper(onFormError: (message: string) => void) {
  const navigate = useNavigate()
  const { total, canAfford, refresh } = useCredits()

  const mutation = useMutation({
    mutationFn: generatePaper,
    onSuccess: (paper) => {
      queryClient.setQueryData(['paper', paper.paper_id], paper)
      queryClient.invalidateQueries({ queryKey: ['papers', 'list'] })
      refresh()
      navigate(`/papers/${paper.paper_id}`)
    },
    onError: (err) => {
      if (
        err instanceof ApiError &&
        (err.payload.error_code === 'ai.parser_failed' ||
          err.payload.error_code === 'ai.no_candidate')
      ) {
        onFormError(
          err.payload.error_code === 'ai.parser_failed'
            ? 'AI 没能理解这个需求，换个说法试试（如"来 5 道现在完成时的选择题"）'
            : '题库里找不到匹配的题，试着放宽题型或考点条件',
        )
      } else {
        toastApiError(err)
      }
    },
  })

  /** 出卷前的本地预检：余额已知且 < 预估价 → 弹充值并返回 false；否则 true。 */
  const guard = (estimatedCost: number | null): boolean => {
    if (!canAfford(estimatedCost)) {
      openCreditsDialog({ required: estimatedCost ?? undefined, available: total ?? undefined })
      return false
    }
    return true
  }

  return {
    generate: (req: GeneratePaperRequest) => mutation.mutate(req),
    guard,
    isPending: mutation.isPending,
    /** 当前可用积分（未加载为 null） */
    credits: total,
  }
}
