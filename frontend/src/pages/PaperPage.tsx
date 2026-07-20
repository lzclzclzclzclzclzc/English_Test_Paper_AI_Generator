import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { usePaper } from '@/hooks/usePaper'
import { useAuth } from '@/hooks/useAuth'
import { useMembership } from '@/hooks/useMembership'
import { recordGrade } from '@/lib/wrongBook'
import { revisePaper } from '@/api/papers'
import { submitAttempt } from '@/api/attempts'
import { ApiError } from '@/api/client'
import { toastApiError } from '@/lib/errors'
import { queryClient } from '@/lib/queryClient'
import type { AnswerDraft } from '@/lib/answers'
import { buildSubmission, listUnanswered } from '@/lib/answers'
import { buildPaperNotices } from '@/lib/paperNotices'
import { PaperSheet } from '@/components/PaperSheet'
import { QuestionCard } from '@/components/QuestionCard'
import { GradeBanner, ScoreStamp } from '@/components/GradeBanner'
import { MemberPill, UpgradeDialog } from '@/components/UpgradeDialog'
import { RequestSummary } from '@/components/RequestSummary'
import { SolutionBlock } from '@/components/SolutionBlock'
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
  const [upgradeReason, setUpgradeReason] = useState<string | null>(null)

  const { locked } = useMembership()
  const { data: user } = useAuth()
  const userId = user?.id ?? 'anon'

  // D4：成绩只活在 mutation state（后端无历史成绩端点，刷新即回到答题态）
  const grade = useMutation({
    mutationFn: submitAttempt,
    onSuccess: (result) => {
      // 列表页的 submitted 标记随交卷改变
      queryClient.invalidateQueries({ queryKey: ['papers', 'list'] })
      // 错题本记账：答错的收进来、答对的清账（仅真实用户，避免串号）
      if (paper && user?.id) {
        recordGrade(user.id, paper, result.items)
      }
    },
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
  const wrongCount = paper.items.filter(
    (item) => resultByIndex.get(item.index)?.is_correct === false,
  ).length

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

  // 错题已在判分时写入错题本，这里直接去错题复习页
  const handleRemediate = () => navigate('/review')

  const unanswered = listUnanswered(paper, answers)
  const notices = buildPaperNotices(paper.metadata)
  // metadata.revised_from：改卷生成的卷可回看原卷（宽容解析，缺失即不显示）
  const revisedFrom =
    typeof paper.metadata?.revised_from === 'string' && paper.metadata.revised_from.trim() !== ''
      ? paper.metadata.revised_from
      : null
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
        <Button
          variant="outline"
          size="sm"
          onClick={() =>
            locked
              ? setUpgradeReason(
                  '重新出卷是会员功能：用一句话让 AI 调整整卷（换题型、换考点、增减题量）。',
                )
              : setReviseOpen(true)
          }
        >
          重新出卷
          {locked && <MemberPill className="ml-1.5" />}
        </Button>
      </div>

      {submitted && (
        <GradeBanner
          earned={earned}
          total={paper.total_score}
          correctCount={correctCount}
          totalCount={paper.items.length}
          wrongCount={wrongCount}
          onRetry={() => {
            grade.reset()
            setAnswers({})
          }}
          onRemediate={handleRemediate}
        />
      )}

      {revisedFrom && (
        <p className="text-[12.5px] text-text-mid">
          本卷由另一份试卷修改而来 ·{' '}
          <Link to={`/papers/${revisedFrom}`} className="text-ink underline underline-offset-2">
            查看原卷
          </Link>
        </p>
      )}

      {/* 生成说明（request 回显 + metadata 里的检索/改写降级提示）：只陈述事实，不打断做题 */}
      <div className="flex flex-col gap-1.5 rounded-md border border-[#d8e0ea] bg-ink-wash px-5 py-3">
        <RequestSummary request={paper.request} />
        {notices.length > 0 && (
          <ul className="flex flex-col gap-0.5 text-[13px] leading-relaxed text-text-mid">
            {notices.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        )}
      </div>

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
                submitted ? (
                  <SolutionBlock
                    question={item.question}
                    sourceQuestionId={item.source_question_id}
                    revisionMode={item.revision_mode}
                    cacheKey={['solution', paper.paper_id, item.index]}
                    locked={locked}
                    userId={userId}
                  />
                ) : undefined
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

      <UpgradeDialog reason={upgradeReason} onClose={() => setUpgradeReason(null)} />

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
