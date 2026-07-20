import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { generatePaper } from '@/api/papers'
import { ApiError } from '@/api/client'
import { toastApiError } from '@/lib/errors'
import { queryClient } from '@/lib/queryClient'
import { useAuth } from '@/hooks/useAuth'
import { useMembership } from '@/hooks/useMembership'
import { consumeQuota, quotaRemaining, FREE_GENERATE_PER_DAY } from '@/lib/quota'
import type { GenerationMode, GeneratePaperRequest } from '@/types/api'

/** 非会员触碰会员模式时的升级文案（guard 返回给 UpgradeDialog）。 */
const MODE_LOCK_REASONS: Record<Exclude<GenerationMode, 'fresh'>, string> = {
  remediation: '错题巩固是会员功能：AI 会围绕你错题本里的题目定向组卷。',
  review: '综合复习是会员功能：AI 会基于你选定时间窗内的答题记录出一份复习卷。',
}

/**
 * 生成试卷的共享逻辑（生成页 / 错题复习页）：
 * 成功后种缓存零请求进卷、失效列表、非会员扣当日配额、导航到新卷；
 * ai.parser_failed / ai.no_candidate 走 onFormError 表单内提示，其余 toast。
 */
export function useGeneratePaper(onFormError: (message: string) => void) {
  const navigate = useNavigate()
  const { data: user } = useAuth()
  const { locked } = useMembership()
  const userId = user?.id ?? 'anon'
  // 消耗配额后 bump，让剩余次数重新计算
  const [, setQuotaTick] = useState(0)
  const freeRemaining = quotaRemaining(userId, 'generate', FREE_GENERATE_PER_DAY)

  const mutation = useMutation({
    mutationFn: generatePaper,
    onSuccess: (paper) => {
      queryClient.setQueryData(['paper', paper.paper_id], paper)
      queryClient.invalidateQueries({ queryKey: ['papers', 'list'] })
      if (locked) {
        consumeQuota(userId, 'generate')
        setQuotaTick((t) => t + 1)
      }
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

  /** 出卷前的会员门槛：返回 UpgradeDialog 文案，null = 放行。模式锁优先于次数限制。 */
  const guard = (mode: GenerationMode): string | null => {
    if (!locked) return null
    if (mode !== 'fresh') return MODE_LOCK_REASONS[mode]
    if (freeRemaining <= 0) {
      return `今日 ${FREE_GENERATE_PER_DAY} 次免费出卷已用完，开通会员后不限次数。`
    }
    return null
  }

  return {
    generate: (req: GeneratePaperRequest) => mutation.mutate(req),
    guard,
    isPending: mutation.isPending,
    locked,
    freeRemaining,
  }
}
