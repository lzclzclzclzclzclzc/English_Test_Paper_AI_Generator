import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, type QueryKey } from '@tanstack/react-query'
import { fetchSolution } from '@/api/solutions'
import { consumeQuota, quotaRemaining, FREE_SOLUTION_PER_DAY } from '@/lib/quota'
import type { RevisedQuestion, RevisionMode } from '@/types/api'
import { Skeleton } from '@/components/ui/skeleton'

interface SolutionBlockProps {
  question: RevisedQuestion
  sourceQuestionId: string
  revisionMode: RevisionMode
  /** 调用方决定缓存身份：试卷页按 (paperId, index)，错题本按 (sourceQuestionId, gradedAt) */
  cacheKey: QueryKey
  /** true = 已确认非会员，AI 解析受每日免费次数限制 */
  locked: boolean
  userId: string
}

/**
 * 单题解析区：question.solution 有值直接展示（不请求、不计配额）；
 * 否则按需 POST /api/solutions，用 enabled:false 的 query 缓存住——
 * 反复展开/收起不重复请求（解析限流 60/min）。
 * 非会员每天限 FREE_SOLUTION_PER_DAY 次 AI 解析。
 */
export function SolutionBlock({
  question,
  sourceQuestionId,
  revisionMode,
  cacheKey,
  locked,
  userId,
}: SolutionBlockProps) {
  const [open, setOpen] = useState(false)
  const [exhausted, setExhausted] = useState(false)
  const preloaded = question.solution

  const solutionQuery = useQuery({
    queryKey: cacheKey,
    queryFn: () =>
      fetchSolution({
        question,
        source_question_id: sourceQuestionId,
        revision_mode: revisionMode,
      }),
    enabled: false,
    staleTime: Infinity,
    retry: false,
  })

  const text = preloaded ?? solutionQuery.data?.solution

  const handleOpen = () => {
    if (!preloaded && !solutionQuery.data) {
      if (locked && quotaRemaining(userId, 'solution', FREE_SOLUTION_PER_DAY) <= 0) {
        setExhausted(true)
        return
      }
      if (locked) consumeQuota(userId, 'solution')
      void solutionQuery.refetch()
    }
    setOpen(true)
  }

  if (exhausted) {
    return (
      <div className="rounded-md border border-[#ece7d9] bg-[#faf8f3] px-4 py-3 text-[13px] text-text-mid">
        今日 {FREE_SOLUTION_PER_DAY} 次免费 AI 解析已用完，
        <Link to="/membership" className="text-ink underline underline-offset-2">
          开通会员
        </Link>
        后不限量查看。
      </div>
    )
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={handleOpen}
        className="self-start rounded-full border border-line-strong bg-sheet px-3 py-1 text-xs text-text-mid transition-colors hover:border-muted-foreground hover:text-foreground"
      >
        查看解析
      </button>
    )
  }

  return (
    <div className="rounded-md border border-[#ece7d9] bg-[#faf8f3] px-4 py-3">
      <div className="mb-1.5 flex items-center justify-between">
        <span className="text-xs font-bold text-ink">解析</span>
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="text-xs text-muted-foreground hover:text-foreground"
        >
          收起
        </button>
      </div>
      {text ? (
        <p className="text-[13.5px] leading-relaxed text-text-mid">{text}</p>
      ) : solutionQuery.isError ? (
        <p className="text-[13px] text-wrong">
          解析获取失败。
          <button
            type="button"
            className="ml-1 underline"
            onClick={() => void solutionQuery.refetch()}
          >
            重试
          </button>
        </p>
      ) : (
        <div className="flex flex-col gap-1.5">
          <p className="text-xs text-text-mid">AI 正在撰写解析…</p>
          <Skeleton className="h-4 w-3/4" />
        </div>
      )}
    </div>
  )
}
