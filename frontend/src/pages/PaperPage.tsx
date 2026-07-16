import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { usePaper } from '@/hooks/usePaper'
import { revisePaper } from '@/api/papers'
import { submitAttempt } from '@/api/attempts'
import { fetchSolution } from '@/api/solutions'
import { ApiError } from '@/api/client'
import { toastApiError } from '@/lib/errors'
import { queryClient } from '@/lib/queryClient'
import type { AnswerDraft } from '@/lib/answers'
import { buildSubmission, listUnanswered } from '@/lib/answers'
import type { PaperItem, WrongItemRef } from '@/types/api'
import type { RemediationHandoff } from '@/types/app'
import { PaperSheet } from '@/components/PaperSheet'
import { QuestionCard } from '@/components/QuestionCard'
import { GradeBanner, ScoreStamp } from '@/components/GradeBanner'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'

/**
 * 薄壳：以 key=paperId 强制重挂载内层——revise 换 id 导航后
 * 本地 state（答案、成绩、对话框）随之清空（计划 D 路由结构）。
 */
export function PaperPageRoute() {
  const { paperId } = useParams<{ paperId: string }>()
  if (!paperId) return null
  return <PaperPageInner key={paperId} paperId={paperId} />
}

function PaperPageInner({ paperId }: { paperId: string }) {
  const navigate = useNavigate()
  const { data: paper, isLoading, error, refetch } = usePaper(paperId)

  // D3：答题草稿。单选存 label；填空/改写存 blankN 字典
  const [answers, setAnswers] = useState<Record<number, AnswerDraft>>({})
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [reviseOpen, setReviseOpen] = useState(false)
  const [reviseInstruction, setReviseInstruction] = useState('')

  // D4：成绩只活在 mutation state（后端无历史成绩端点，刷新即回到答题态）
  const grade = useMutation({
    mutationFn: submitAttempt,
    // 列表页的 submitted 标记随交卷改变
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['papers', 'list'] }),
    onError: toastApiError,
  })
  const phase = grade.isPending ? 'submitting' : grade.data ? 'submitted' : 'answering'

  const revise = useMutation({
    mutationFn: revisePaper,
    onSuccess: (newPaper) => {
      queryClient.setQueryData(['paper', newPaper.paper_id], newPaper)
      queryClient.invalidateQueries({ queryKey: ['papers', 'list'] })
      navigate(`/papers/${newPaper.paper_id}`)
    },
    onError: toastApiError,
  })

  const resultByIndex = useMemo(
    () => new Map((grade.data?.items ?? []).map((r) => [r.index, r])),
    [grade.data],
  )

  if (isLoading) {
    return (
      <div className="mx-auto flex max-w-[880px] flex-col gap-4 px-6 pt-10">
        <Skeleton className="mx-auto h-9 w-2/3" />
        <Skeleton className="h-72 w-full" />
      </div>
    )
  }

  if (error || !paper) {
    const notFound = error instanceof ApiError && error.status === 404
    return (
      <div className="mx-auto flex max-w-[880px] flex-col items-center gap-4 px-6 pt-20 text-center">
        <p className="font-serif text-lg font-bold text-foreground">
          {notFound ? '没有找到这份试卷' : '试卷加载失败'}
        </p>
        {notFound && (
          <p className="-mt-2 text-[13px] text-text-mid">
            链接可能已失效，或这份卷不在当前账号下
          </p>
        )}
        {notFound ? (
          <Button asChild variant="outline">
            <Link to="/">去生成新试卷</Link>
          </Button>
        ) : (
          <Button variant="outline" onClick={() => refetch()}>
            重试
          </Button>
        )}
      </div>
    )
  }

  const submitted = phase === 'submitted'
  const earned = paper.items
    .filter((item) => resultByIndex.get(item.index)?.is_correct)
    .reduce((sum, item) => sum + item.score, 0)
  const correctCount = paper.items.filter(
    (item) => resultByIndex.get(item.index)?.is_correct,
  ).length
  const wrongItemRefs: WrongItemRef[] = paper.items
    .filter((item) => resultByIndex.get(item.index)?.is_correct === false)
    .map((item) => ({
      knowledge_point_ids: item.question.knowledge_point_ids,
      question_type: item.question.question_type,
    }))

  const doSubmit = () => {
    setConfirmOpen(false)
    grade.mutate({ paper_id: paper.paper_id, items: buildSubmission(paper, answers) })
  }

  const handleSubmitClick = () => {
    if (listUnanswered(paper, answers).length > 0) {
      setConfirmOpen(true)
    } else {
      doSubmit()
    }
  }

  const handleRemediate = () => {
    const handoff: RemediationHandoff = {
      wrongItems: wrongItemRefs,
      sourcePaperTitle: paper.title,
    }
    navigate('/', { state: { remediation: handoff } })
  }

  const unanswered = listUnanswered(paper, answers)
  const generatedAt = new Date(paper.generated_at).toLocaleString('zh-CN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  })

  return (
    <div className="mx-auto flex max-w-[880px] flex-col gap-4 px-6 pt-8">
      {/* 卷面之上的现代控件区（Spec F：纸上的东西不发光、控件不仿古） */}
      <div className="flex items-center justify-between">
        <Button asChild variant="ghost" size="sm">
          <Link to="/">← 生成新试卷</Link>
        </Button>
        <Button variant="outline" size="sm" onClick={() => setReviseOpen(true)}>
          重新出卷
        </Button>
      </div>

      {submitted && (
        <GradeBanner
          earned={earned}
          total={paper.total_score}
          correctCount={correctCount}
          totalCount={paper.items.length}
          wrongCount={wrongItemRefs.length}
          onRetry={() => {
            grade.reset()
            setAnswers({})
          }}
          onRemediate={handleRemediate}
        />
      )}

      <PaperSheet
        title={paper.title}
        meta={`共 ${paper.items.length} 题 · 满分 ${paper.total_score} 分 · ${generatedAt}`}
        stamp={submitted ? <ScoreStamp earned={earned} /> : undefined}
      >
        <div className="divide-y divide-dashed divide-line">
          {paper.items.map((item) => (
            <QuestionCard
              key={item.index}
              item={item}
              mode={submitted ? 'review' : 'answering'}
              value={answers[item.index]}
              onChange={(v) => setAnswers((prev) => ({ ...prev, [item.index]: v }))}
              result={resultByIndex.get(item.index)}
              solutionSlot={
                submitted ? <SolutionBlock paperId={paper.paper_id} item={item} /> : undefined
              }
            />
          ))}
        </div>

        {!submitted && (
          <div className="mt-8 flex justify-center">
            <Button
              size="lg"
              className="px-8 font-bold tracking-[4px]"
              disabled={phase === 'submitting'}
              onClick={handleSubmitClick}
            >
              {phase === 'submitting' ? '判分中…' : '交 卷'}
            </Button>
          </div>
        )}
      </PaperSheet>

      {/* 漏答确认 */}
      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>还有题目未作答</DialogTitle>
            <DialogDescription>
              第 {unanswered.join('、')} 题未作答或未填完，交卷后将按错误计分。
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmOpen(false)}>
              继续作答
            </Button>
            <Button onClick={doSubmit}>仍要交卷</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 重新出 */}
      <Dialog open={reviseOpen} onOpenChange={setReviseOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>重新出卷</DialogTitle>
            <DialogDescription>
              告诉 AI 想怎么改（换题型、换考点、增减题量……），会生成一份新试卷
              {!submitted && Object.keys(answers).length > 0 && '；当前已填的答案不会保留'}
              。
            </DialogDescription>
          </DialogHeader>
          <Textarea
            rows={3}
            placeholder="例如：把选择题换成词形转换"
            value={reviseInstruction}
            onChange={(e) => setReviseInstruction(e.target.value)}
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setReviseOpen(false)}>
              保留这份卷
            </Button>
            <Button
              disabled={reviseInstruction.trim() === '' || revise.isPending}
              onClick={() =>
                revise.mutate({
                  paper_id: paper.paper_id,
                  user_instruction: reviseInstruction.trim(),
                })
              }
            >
              {revise.isPending ? '正在组卷…' : '重新出卷'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

/**
 * 单题解析区（成绩视图）：question.solution 有值直接展示；
 * 否则按需 POST /api/solutions，用 enabled:false 的 query 缓存住——
 * 反复展开/收起不重复请求（解析限流 60/min）。
 */
function SolutionBlock({ paperId, item }: { paperId: string; item: PaperItem }) {
  const [open, setOpen] = useState(false)
  const preloaded = item.question.solution

  const solutionQuery = useQuery({
    queryKey: ['solution', paperId, item.index],
    queryFn: () =>
      fetchSolution({
        question: item.question,
        source_question_id: item.source_question_id,
        revision_mode: item.revision_mode,
      }),
    enabled: false,
    staleTime: Infinity,
    retry: false,
  })

  const text = preloaded ?? solutionQuery.data?.solution

  const handleOpen = () => {
    setOpen(true)
    if (!preloaded && !solutionQuery.data) void solutionQuery.refetch()
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
