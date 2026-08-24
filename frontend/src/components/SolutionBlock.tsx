import { useState } from 'react'
import { useQuery, type QueryKey } from '@tanstack/react-query'
import { ApiError } from '@/api/client'
import { fetchSolution } from '@/api/solutions'
import { CreditHint } from '@/components/CreditHint'
import { invalidateCredits } from '@/hooks/useCredits'
import { toastApiError } from '@/lib/errors'
import type { RevisedQuestion, RevisionMode, UserAnswerValue } from '@/types/api'
import { Skeleton } from '@/components/ui/skeleton'

interface SolutionBlockProps {
  question: RevisedQuestion
  sourceQuestionId: string
  revisionMode: RevisionMode
  /** 调用方决定缓存身份：试卷页按 (paperId, index)，错题本按 (sourceQuestionId, gradedAt) */
  cacheKey: QueryKey
  /** 用户答错时传入所选答案，解析会解释为何该答案错误 */
  userAnswer?: UserAnswerValue | null
}

/**
 * 单题解析（handoff 第 6 屏）：「查看解析」下划线文字按钮 → kk-rise 展开
 * 细线圆角框，顶部小标签「AI 讲解 · 按需生成」。
 * question.solution 有值直接展示（不请求、不扣积分）；否则按需 POST /api/solutions，
 * enabled:false 的 query 缓存住——反复展开/收起不重复请求、不重复扣费（解析限流 60/min）。
 * 每次生成按价目表扣积分（solution）；余额不足 402 → 充值弹窗。
 */
export function SolutionBlock({
  question,
  sourceQuestionId,
  revisionMode,
  cacheKey,
  userAnswer,
}: SolutionBlockProps) {
  const [open, setOpen] = useState(false)
  const preloaded = question.solution

  const solutionQuery = useQuery({
    queryKey: cacheKey,
    queryFn: () =>
      fetchSolution({
        question,
        source_question_id: sourceQuestionId,
        revision_mode: revisionMode,
        user_answer: userAnswer ?? null,
      }),
    enabled: false,
    staleTime: Infinity,
    retry: false,
  })

  const text = preloaded ?? solutionQuery.data?.solution

  const request = async () => {
    const result = await solutionQuery.refetch()
    if (result.error) {
      // 402 积分不足 → 充值弹窗并收起；其他错误留在面板里给「重试」
      if (result.error instanceof ApiError && result.error.payload.error_code === 'credits.insufficient') {
        toastApiError(result.error)
        setOpen(false)
      }
    } else {
      invalidateCredits()
    }
  }

  const handleOpen = () => {
    if (!preloaded && !solutionQuery.data) void request()
    setOpen(true)
  }

  if (!open) {
    return (
      <span className="flex items-center gap-2 self-start">
        <button
          type="button"
          onClick={handleOpen}
          className="font-ui text-[13px] text-muted-ink underline decoration-ink-30 underline-offset-4 transition-colors hover:text-accent hover:decoration-accent"
        >
          查看解析
        </button>
        {!preloaded && !solutionQuery.data && <CreditHint action="solution" />}
      </span>
    )
  }

  return (
    <div className="kk-rise rounded-md border border-hairline px-5 py-4">
      <div className="mb-2 flex items-center justify-between">
        <span className="kicker">
          AI 讲解 · 按需生成
        </span>
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="font-ui text-[12px] text-quiet transition-colors hover:text-accent"
        >
          收起解析
        </button>
      </div>
      {text ? (
        <p className="text-[15px] leading-[1.95] text-muted-ink">{text}</p>
      ) : solutionQuery.isError ? (
        <p className="text-[13px] text-accent">
          解析获取失败。
          <button
            type="button"
            className="ml-1 underline"
            onClick={() => void request()}
          >
            重试
          </button>
        </p>
      ) : (
        <div className="flex flex-col gap-1.5">
          <p className="font-ui text-[12px] text-muted-ink">AI 正在撰写解析…</p>
          <Skeleton className="h-4 w-3/4" />
        </div>
      )}
    </div>
  )
}
