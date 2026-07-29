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
 * 单题解析（handoff 第 6 屏）：「查看解析」下划线文字按钮 → kk-rise 展开
 * 细线圆角框，顶部小标签 `POST /API/SOLUTIONS · 按需生成`。
 * question.solution 有值直接展示（不请求、不计配额）；否则按需 POST /api/solutions，
 * enabled:false 的 query 缓存住——反复展开/收起不重复请求（解析限流 60/min）。
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
      <div className="rounded-md border border-hairline px-4 py-3 text-[13px] text-muted-ink">
        今日 {FREE_SOLUTION_PER_DAY} 次免费 AI 解析已用完，
        <Link to="/membership" className="text-accent underline underline-offset-2">
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
        className="self-start text-[13px] text-muted-ink underline decoration-ink-30 underline-offset-4 transition-colors hover:text-accent hover:decoration-accent"
      >
        查看解析
      </button>
    )
  }

  return (
    <div className="kk-rise rounded-md border border-hairline px-5 py-4">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-[10.5px] font-bold tracking-[0.14em] text-quiet">
          POST /API/SOLUTIONS · 按需生成
        </span>
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="text-[12px] text-quiet transition-colors hover:text-accent"
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
            onClick={() => void solutionQuery.refetch()}
          >
            重试
          </button>
        </p>
      ) : (
        <div className="flex flex-col gap-1.5">
          <p className="text-[12px] text-muted-ink">AI 正在撰写解析…</p>
          <Skeleton className="h-4 w-3/4" />
        </div>
      )}
    </div>
  )
}
