import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { usePaper } from '@/hooks/usePaper'
import { useAuth } from '@/hooks/useAuth'
import { useMembership } from '@/hooks/useMembership'
import { recordGrade } from '@/lib/wrongBook'
import { revisePaper, generatePaper } from '@/api/papers'
import { submitAttempt, getAttemptByPaper } from '@/api/attempts'
import { ApiError } from '@/api/client'
import { toastApiError } from '@/lib/errors'
import { queryClient } from '@/lib/queryClient'
import { stopAll as stopTTS } from '@/lib/tts'
import type { AnswerDraft } from '@/lib/answers'
import { buildSubmission, formatCorrectAnswer, listUnanswered } from '@/lib/answers'
import { buildPaperNotices } from '@/lib/paperNotices'
import { claimPendingTimer } from '@/lib/paperTimer'
import { AnswerCard } from '@/components/AnswerCard'
import { PaperTimer } from '@/components/PaperTimer'
import { PassageBlock } from '@/components/PassageBlock'
import { QuestionCard } from '@/components/QuestionCard'
import { GradeBanner } from '@/components/GradeBanner'
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
import type { GradeSubmissionResponse, PaperItem } from '@/types/api'
import { PATHS } from '@/lib/paths'

/** 按 passage_id 分组：同组小题共享一段材料，PassageBlock 只渲染一次。 */
function groupByPassage(items: PaperItem[]): Array<{ key: string; passageId: string | null; items: PaperItem[] }> {
  const groups: Array<{ key: string; passageId: string | null; items: PaperItem[] }> = []
  const seen = new Map<string, number>()
  for (const item of items) {
    const pid = item.question.passage_id ?? null
    const key = pid ?? `solo-${item.index}`
    const idx = seen.get(key)
    if (idx !== undefined) {
      groups[idx]?.items.push(item)
    } else {
      seen.set(key, groups.length)
      groups.push({ key, passageId: pid, items: [item] })
    }
  }
  return groups
}

/**
 * 薄壳：以 key=paperId 强制重挂载内层——revise 换 id 导航后
 * 本地 state（答案、成绩、面板）随之清空（计划 D 路由结构）。
 */
export function PaperPageRoute() {
  const { paperId } = useParams<{ paperId: string }>()
  if (!paperId) return null
  return <PaperPageInner key={paperId} paperId={paperId} />
}

function PaperPageInner({ paperId }: { paperId: string }) {
  const navigate = useNavigate()
  const { data: paper, isLoading, error, refetch } = usePaper(paperId)

  // 离开试卷页面时停止所有 TTS 播放
  useEffect(() => () => stopTTS(), [])

  // D3：答题草稿。单选存 label；填空/改写存 blankN 字典
  const [answers, setAnswers] = useState<Record<number, AnswerDraft>>({})
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [reviseOpen, setReviseOpen] = useState(false)
  const [reviseInstruction, setReviseInstruction] = useState('')
  const [upgradeReason, setUpgradeReason] = useState<string | null>(null)
  // 点「再做一遍」后置 true，强制忽略历史结果、回到答题态
  const [redoing, setRedoing] = useState(false)
  // 教师版打印：先渲染 print-only 的参考答案区，再触发 window.print
  const [teacherPrint, setTeacherPrint] = useState(false)
  // 限时模式：挂载时一次性取走出卷入口登记的分钟数（刷新不重启计时）
  const [timerMinutes] = useState(() => claimPendingTimer())
  const [timeUpOpen, setTimeUpOpen] = useState(false)

  useEffect(() => {
    if (!teacherPrint) return
    window.print()
    setTeacherPrint(false)
  }, [teacherPrint])

  const { locked } = useMembership()
  const { data: user } = useAuth()
  const userId = user?.id ?? 'anon'

  // 错题巩固：用当前试卷答错的题定向组卷。不自动跳转——完成后由按钮点击跳转
  const remediation = useMutation({
    mutationFn: generatePaper,
    onSuccess: (newPaper) => {
      queryClient.setQueryData(['paper', newPaper.paper_id], newPaper)
      queryClient.invalidateQueries({ queryKey: ['papers', 'list'] })
    },
    onError: toastApiError,
  })

  // 打开时拉取上次答题结果（未交卷返回 null），用于复盘展示
  const history = useQuery({
    queryKey: ['attempt', 'by-paper', paperId],
    queryFn: () => getAttemptByPaper(paperId),
    staleTime: 30_000,
  })

  // D4：本次交卷成绩活在 mutation state
  const grade = useMutation({
    mutationFn: submitAttempt,
    onSuccess: (result) => {
      // 列表页的 submitted 标记随交卷改变
      queryClient.invalidateQueries({ queryKey: ['papers', 'list'] })
      // 更新历史结果缓存，重新打开可直接复盘
      queryClient.setQueryData(['attempt', 'by-paper', paperId], result)
      // 错题本记账：答错的收进来、答对的清账（仅真实用户，避免串号）
      if (paper && user?.id) {
        recordGrade(user.id, paper, result.items)
      }
    },
    onError: toastApiError,
  })

  // 展示用结果：本次交卷优先，否则用历史结果（正在重做时忽略历史）
  const shownResult: GradeSubmissionResponse | null | undefined =
    grade.data ?? (redoing ? null : history.data)
  const phase = grade.isPending ? 'submitting' : shownResult ? 'submitted' : 'answering'

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
    () => new Map((shownResult?.items ?? []).map((r) => [r.index, r])),
    [shownResult],
  )

  if (isLoading || history.isLoading) {
    return (
      <div className="mx-auto flex w-full max-w-[760px] flex-col gap-4">
        <Skeleton className="h-9 w-2/3" />
        <Skeleton className="h-72 w-full" />
      </div>
    )
  }

  if (error || !paper) {
    const notFound = error instanceof ApiError && error.status === 404
    return (
      <div className="mx-auto flex w-full max-w-[760px] flex-col items-start gap-4 pt-10">
        <p className="text-[18px] text-ink">
          {notFound ? '没有找到这份试卷' : '试卷加载失败'}
        </p>
        {notFound && (
          <p className="-mt-2 text-[13px] text-muted-ink">
            链接可能已失效，或这份卷不在当前账号下
          </p>
        )}
        {notFound ? (
          <Button asChild variant="outline">
            <Link to={PATHS.dashboard}>去生成新试卷</Link>
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
  const correctCount = paper.items.filter(
    (item) => resultByIndex.get(item.index)?.is_correct,
  ).length
  const wrongCount = paper.items.filter(
    (item) => resultByIndex.get(item.index)?.is_correct === false,
  ).length

  const doSubmit = () => {
    setConfirmOpen(false)
    stopTTS()
    grade.mutate({ paper_id: paper.paper_id, items: buildSubmission(paper, answers) })
  }

  const handleSubmitClick = () => {
    if (listUnanswered(paper, answers).length > 0) {
      setConfirmOpen(true)
    } else {
      doSubmit()
    }
  }

  // 错题巩固：用当前试卷答错的题（考点+题型）定向生成一份新的巩固卷
  const handleRemediate = () => {
    const wrongItems = paper.items
      .filter((item) => resultByIndex.get(item.index)?.is_correct === false)
      .map((item) => ({
        knowledge_point_ids: item.question.knowledge_point_ids,
        question_type: item.question.question_type,
      }))
    if (wrongItems.length === 0) return
    if (locked) {
      setUpgradeReason('错题巩固是会员功能：AI 会围绕你这份卷做错的题定向组卷。')
      return
    }
    remediation.mutate({
      user_query: '针对我这份试卷里做错的题目，出一份针对性的巩固练习',
      mode: 'remediation',
      wrong_items: wrongItems,
    })
  }

  const unanswered = listUnanswered(paper, answers)
  const answeredCount = paper.items.length - unanswered.length
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
    <div className="mx-auto flex w-full max-w-[1104px] justify-center gap-10">
      {/* 左：760px 内容列（大屏与右栏一起居中，窄屏右栏折叠后单列居中） */}
      <div className="min-w-0 max-w-[760px] flex-1">
        <p className="font-ui text-[11px] tracking-[0.1em] text-quiet">
          PAPER · {paper.paper_id.slice(0, 8)}
        </p>
        <h1 className="mt-3 text-[38px] font-normal leading-snug text-ink [font-family:var(--font-display)] [text-wrap:balance]">
          {paper.title}
        </h1>
        <p className="mt-2 font-ui text-[13px] tabular-nums text-quiet">
          {generatedAt} · 共 {paper.items.length} 题
        </p>

        <div className="mt-5 flex items-center gap-2.5 border-b border-hairline pb-6 print:hidden">
          <Button variant="outline" size="sm" asChild>
            <Link to="/papers">← 历史试卷</Link>
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              if (locked) {
                setUpgradeReason(
                  '重新出卷是会员功能：用一句话让 AI 调整整卷（换题型、换考点、增减题量）。',
                )
              } else {
                setReviseOpen((v) => !v)
              }
            }}
          >
            重新生成
            {locked && <MemberPill className="ml-1.5" />}
          </Button>
          <Button variant="outline" size="sm" onClick={() => window.print()}>
            打印学生卷
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              if (locked) {
                setUpgradeReason('教师版试卷含完整参考答案，是会员功能。')
              } else {
                setTeacherPrint(true)
              }
            }}
          >
            打印教师版
            {locked && <MemberPill className="ml-1.5" />}
          </Button>
        </div>

        {/* 限时模式：细线一行（提醒制，不强制收卷）；交卷后整行消失 */}
        {timerMinutes !== null && phase !== 'submitted' && (
          <div className="mt-4 inline-flex items-center gap-3 rounded-sm border border-hairline px-3 py-2 print:hidden">
            <PaperTimer
              minutes={timerMinutes}
              running={phase === 'answering'}
              onExpire={() => setTimeUpOpen(true)}
            />
            <span className="font-ui text-[12px] text-quiet">限时模式 · 到时提醒，不强制收卷</span>
          </div>
        )}

        {/* 重新生成面板（handoff 第 5 屏）：细线圆角框，POST /api/papers/revise */}
        {reviseOpen && (
          <div className="kk-rise mt-6 flex max-w-[44rem] flex-col gap-3 rounded-md border border-hairline p-5 print:hidden">
            <span className="font-ui text-[10.5px] font-bold tracking-[0.14em] text-quiet">
              重新出卷 · 原卷保留
            </span>
            <textarea
              rows={2}
              placeholder="告诉 AI 想怎么改：换题型、换考点、增减题量……会生成一份新试卷"
              value={reviseInstruction}
              onChange={(e) => setReviseInstruction(e.target.value)}
              className="w-full resize-none rounded-[3px] border border-ink-20 bg-transparent px-3 py-2.5 text-[15px] leading-[1.8] text-ink outline-none transition-colors placeholder:text-quiet focus:border-accent"
            />
            {!submitted && Object.keys(answers).length > 0 && (
              <p className="text-[12px] text-quiet">当前已填的答案不会保留</p>
            )}
            <div className="flex items-center gap-2.5">
              <Button
                size="sm"
                disabled={reviseInstruction.trim() === '' || revise.isPending}
                onClick={() =>
                  revise.mutate({
                    paper_id: paper.paper_id,
                    user_instruction: reviseInstruction.trim(),
                  })
                }
              >
                {revise.isPending ? '正在组卷…' : '重新生成一份新卷'}
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setReviseOpen(false)}>
                取消
              </Button>
            </div>
          </div>
        )}

        {submitted && (
          <div className="mt-6 print:hidden">
            <GradeBanner
              correctCount={correctCount}
              totalCount={paper.items.length}
              wrongCount={wrongCount}
              onRetry={() => {
                grade.reset()
                remediation.reset()
                setAnswers({})
                setRedoing(true)
              }}
              onRemediate={handleRemediate}
              remediating={remediation.isPending}
              remediatedPaperId={remediation.data?.paper_id ?? null}
              onOpenRemediation={() => {
                if (remediation.data) navigate(`/papers/${remediation.data.paper_id}`)
              }}
            />
          </div>
        )}

        {/* 生成说明（request 回显 + metadata 里的检索/改写降级提示）：只陈述事实，不打断做题 */}
        <div className="mt-5 flex flex-col gap-1.5 print:hidden">
          <RequestSummary request={paper.request} />
          {revisedFrom && (
            <p className="text-[12.5px] text-quiet">
              本卷由另一份试卷修改而来 ·{' '}
              <Link
                to={`/papers/${revisedFrom}`}
                className="text-accent underline underline-offset-2"
              >
                查看原卷
              </Link>
            </p>
          )}
          {notices.length > 0 && (
            <ul className="flex flex-col gap-0.5 text-[12.5px] leading-relaxed text-quiet">
              {notices.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
          )}
          {paper.request.total_questions > paper.items.length && (
            <p className="text-[12.5px] leading-relaxed text-quiet">
              本卷实际组入 {paper.items.length} 题（要求 {paper.request.total_questions} 题）
              ——该考点真题库存有限，已如实组卷；想要足量可点「重新生成」换成全新出题。
            </p>
          )}
        </div>

        <div className="mt-6 flex flex-col gap-4">
          {groupByPassage(paper.items).map((group) => {
            const passage = group.passageId ? (group.items[0]?.question.passage_json ?? null) : null
            const isReading = passage?.kind === 'reading'
            // 阅读首字母填空：ReadingFirstBlankField 自包含渲染整篇文章（空位内联），
            // 无需再渲染独立的 PassageBlock，避免重复显示文章。
            const isFirstBlank = group.items[0]?.question.question_type === 'reading_first_blank'
            const mode = submitted ? 'review' : 'answering'
            const questionList = (
              <div className="flex min-w-0 flex-col gap-4">
                {group.items.map((item) => (
                  <QuestionCard
                    key={item.index}
                    item={item}
                    mode={mode}
                    value={answers[item.index]}
                    onChange={(v) => setAnswers((prev) => ({ ...prev, [item.index]: v }))}
                    result={resultByIndex.get(item.index)}
                    solutionSlot={
                      submitted ? (
                        <div className="print:hidden">
                          <SolutionBlock
                            question={item.question}
                            sourceQuestionId={item.source_question_id}
                            revisionMode={item.revision_mode}
                            cacheKey={['solution', paper.paper_id, item.index]}
                            locked={locked}
                            userId={userId}
                            userAnswer={(() => {
                              const r = resultByIndex.get(item.index)
                              if (!r || r.is_correct) return null
                              return r.user_answer ?? null
                            })()}
                          />
                        </div>
                      ) : undefined
                    }
                  />
                ))}
              </div>
            )
            // 阅读理解：左右分栏（左 sticky 文章卡，右题目卡列）
            // 阅读首字母填空除外——其文章已由 ReadingFirstBlankField 内联渲染
            if (isReading && !isFirstBlank && passage) {
              return (
                <div key={group.key} className="lg:grid lg:grid-cols-[5fr_4fr] lg:gap-4 max-lg:flex max-lg:flex-col max-lg:gap-4">
                  <div className="lg:sticky lg:top-10 lg:max-h-[calc(100vh-5rem)] lg:self-start lg:overflow-y-auto">
                    <PassageBlock passage={passage} mode={mode} />
                  </div>
                  {questionList}
                </div>
              )
            }
            // 听力 / 无材料：上下垂直布局（材料卡在题目卡上方）
            return (
              <div key={group.key} className="flex flex-col gap-4">
                {passage && !isFirstBlank && <PassageBlock passage={passage} mode={mode} />}
                {questionList}
              </div>
            )
          })}
        </div>

        {!submitted && (
          <div className="mt-8 flex items-center gap-4 print:hidden">
            <button
              type="button"
              disabled={phase === 'submitting'}
              onClick={handleSubmitClick}
              className="rounded-sm border border-accent bg-wash px-7 py-3 font-ui text-[15px] tracking-[0.06em] text-ink transition-colors hover:text-accent disabled:pointer-events-none disabled:opacity-60"
            >
              {phase === 'submitting' ? '判分中…' : '提交判分'}
            </button>
            <span className="font-ui text-[13px] tabular-nums text-quiet">
              已答 {answeredCount} 题，未答 {unanswered.length} 题
            </span>
          </div>
        )}
        {/* 教师版打印专用：参考答案汇总（屏幕上不渲染） */}
        {teacherPrint && (
          <section className="hidden print:block">
            <h2 className="mt-10 border-t border-hairline pt-6 text-[20px] text-ink [font-family:var(--font-display)]">
              参考答案（教师版）
            </h2>
            <ol className="mt-3 flex flex-col gap-1 text-[13.5px] leading-[1.9] text-ink">
              {paper.items.map((item) => (
                <li key={item.index}>
                  {item.index}. {formatCorrectAnswer(item.question.answer)}
                </li>
              ))}
            </ol>
          </section>
        )}
      </div>

      {/* 右：280px 粘顶答题卡。作答态标已答/未答，复盘态标对/错 + 元信息 */}
      <div className="contents print:hidden">
        <AnswerCard paper={paper} answers={answers} results={submitted ? resultByIndex : null} />
      </div>

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

      {/* 限时到点提醒：可交可续，不强制 */}
      <Dialog open={timeUpOpen} onOpenChange={setTimeUpOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>时间到了</DialogTitle>
            <DialogDescription>可以现在交卷，也可以继续作答。</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setTimeUpOpen(false)}>
              继续作答
            </Button>
            <Button
              onClick={() => {
                setTimeUpOpen(false)
                handleSubmitClick()
              }}
            >
              现在交卷
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <UpgradeDialog reason={upgradeReason} onClose={() => setUpgradeReason(null)} />
    </div>
  )
}
