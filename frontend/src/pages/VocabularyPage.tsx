import { useEffect, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { getVocabularyToday, judgeVocabulary, updateVocabularySettings } from '@/api/vocabulary'
import { PageHeader } from '@/components/PageHeader'
import { StatTile } from '@/components/StatTile'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { queryClient } from '@/lib/queryClient'
import type { VocabularyJudgmentResponse, VocabularyRating } from '@/types/api'
import {
  formatVocabularyMeanings,
  isVocabularyExamplePlaceholder,
  vocabularyNextLabel,
  vocabularyPhaseLabel,
} from '@/lib/vocabularyDisplay'

const RATING_BUTTONS: Array<{ value: VocabularyRating; label: string; note: string; variant: 'default' | 'outline' }> = [
  { value: 'known', label: '认识', note: '进入长期复习', variant: 'default' },
  { value: 'fuzzy', label: '模糊', note: '今天会再出现', variant: 'outline' },
  { value: 'forgot', label: '不认识', note: '今天会再出现', variant: 'outline' },
]

function formatDueDate(value: string) {
  return new Intl.DateTimeFormat('zh-CN', { month: 'numeric', day: 'numeric' }).format(new Date(value))
}

export function VocabularyPage() {
  const navigate = useNavigate()
  const [judgment, setJudgment] = useState<VocabularyJudgmentResponse | null>(null)
  const [loadingNext, setLoadingNext] = useState(false)
  const [moreTarget, setMoreTarget] = useState(30)
  const today = useQuery({ queryKey: ['vocabulary', 'today'], queryFn: getVocabularyToday })
  const card = today.data?.current_card
  const judge = useMutation({
    mutationFn: (rating: VocabularyRating) => judgeVocabulary({ word_id: card!.word_id, rating }),
    onSuccess: (result) => {
      setJudgment(result)
      void queryClient.invalidateQueries({ queryKey: ['vocabulary', 'today'] })
    },
  })
  const addMore = useMutation({
    mutationFn: () => updateVocabularySettings(moreTarget),
    onSuccess: async () => {
      setJudgment(null)
      await queryClient.invalidateQueries({ queryKey: ['vocabulary'] })
      await today.refetch()
    },
  })

  const next = async () => {
    setJudgment(null)
    setLoadingNext(true)
    await today.refetch()
    setLoadingNext(false)
  }

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target
      if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement) return
      if (judgment) {
        if (event.key === 'Enter') {
          event.preventDefault()
          void next()
        }
        return
      }
      if (!card || judge.isPending) return
      const rating = ({ '1': 'known', '2': 'fuzzy', '3': 'forgot' } as const)[event.key as '1' | '2' | '3']
      if (rating) {
        event.preventDefault()
        judge.mutate(rating)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [card, judge, judgment])

  useEffect(() => {
    if (today.data) setMoreTarget(Math.min(50, today.data.daily_new_limit + 10))
  }, [today.data?.daily_new_limit])

  if (today.isLoading || loadingNext) return <Skeleton className="h-80 w-full" />
  if (today.isError || !today.data) {
    return <div className="border-t border-hairline pt-8 text-sm text-muted-ink">今日单词任务加载失败，请稍后重试。</div>
  }

  const { counts, phase } = today.data
  const initialTotal = counts.scheduled_review_total + counts.new_total
  const initialCompleted = counts.scheduled_review_completed + counts.new_completed
  const nextLabel = judgment ? vocabularyNextLabel(judgment.phase) : ''

  if (phase === 'completed' && !judgment) {
    return (
      <div className="flex max-w-[42rem] flex-col gap-8">
        <PageHeader title="今日任务完成" intro="新词、到期复习和今日再复习均已完成。" />
        <section className="border-t border-hairline pt-7">
          <div className="grid gap-3 sm:grid-cols-3">
            <StatTile label="今日新词" value={counts.new_completed} />
            <StatTile label="到期复习" value={counts.scheduled_review_completed} />
            <StatTile label="再复习通过" value={counts.retry_completed} />
          </div>
          <div className="mt-8 border-t border-hairline pt-6">
            <h2 className="font-heading text-[17px] font-bold text-ink">继续背新词</h2>
            <p className="mt-2 text-sm leading-6 text-muted-ink">提高今日目标后，系统会立刻按国家核心词优先的顺序补发新词。</p>
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <input className="h-8 w-24 rounded-sm border border-ink-20 bg-transparent px-2 text-ink outline-none focus:border-ink" type="number" min="10" max="50" value={moreTarget} onChange={(event) => setMoreTarget(Number(event.target.value))} />
              <span className="text-sm text-muted-ink">词 / 天</span>
              <Button disabled={addMore.isPending || moreTarget <= today.data.daily_new_limit || moreTarget > 50} onClick={() => addMore.mutate()}>
                {addMore.isPending ? '正在追加…' : '开始背更多'}
              </Button>
            </div>
            {addMore.isError && <p className="mt-3 text-sm text-accent">追加失败，请稍后重试。</p>}
            {moreTarget >= 50 && <p className="mt-3 text-xs text-quiet">今日目标上限为 50 词。</p>}
          </div>
          <div className="mt-7 flex gap-3"><Button onClick={() => navigate('/vocabulary/progress')}>查看进度</Button><Button variant="outline" onClick={() => navigate('/')}>返回首页</Button></div>
        </section>
      </div>
    )
  }

  return (
    <div className="flex max-w-[42rem] flex-col gap-8">
      <PageHeader title="背单词" intro="先凭第一反应判断熟悉度，再确认释义；模糊和不认识的词会在今天再次出现。" />
      <section className="border-t border-hairline pt-7">
        <div className="kicker flex items-center justify-between gap-4" aria-live="polite">
          <span>{vocabularyPhaseLabel(phase)}</span>
          {phase === 'same_day_retry'
            ? <span>待通过 {counts.retry_pending} 词</span>
            : <span>{initialCompleted + 1} / {initialTotal}</span>}
        </div>

        {judgment ? (
          <div className="kk-rise mt-10">
            <p className="text-4xl leading-tight text-ink [font-family:var(--font-question)]">{judgment.detail.term}</p>
            <div className="mt-7 border-t border-hairline pt-6">
              <p className="text-sm text-accent">{judgment.detail.part_of_speech}</p>
              <p className="mt-2 text-xl leading-relaxed text-ink">{formatVocabularyMeanings(judgment.detail.meanings)}</p>
              {isVocabularyExamplePlaceholder(judgment.detail.example_en, judgment.detail.term) ? (
                <p className="mt-7 border-l-2 border-accent/50 pl-4 text-sm leading-7 text-quiet">例句正在整理，暂不展示示范模板。</p>
              ) : (
                <blockquote className="mt-7 border-l-2 border-accent/50 pl-4 text-[15px] leading-7 text-muted-ink">
                  <p>{judgment.detail.example_en}</p>
                  <p className="mt-1 text-[13px] text-quiet">{judgment.detail.example_zh}</p>
                </blockquote>
              )}
            </div>
            <p className="mt-7 text-sm text-muted-ink" aria-live="polite">
              {judgment.added_to_same_day_retry
                ? '已加入今日再复习，稍后会再次出现。'
                : `认识，下一次复习预计在 ${formatDueDate(judgment.next_due_at)}。`}
            </p>
            <div className="mt-7 flex flex-wrap gap-3">
              <Button onClick={() => { if (judgment.phase === 'completed') navigate('/vocabulary/progress'); else void next() }}>{nextLabel}</Button>
              <Button variant="outline" onClick={() => navigate('/vocabulary/progress')}>稍后继续</Button>
            </div>
          </div>
        ) : card ? (
          <div className="kk-rise mt-14">
            <p className="text-center text-5xl leading-tight text-ink [font-family:var(--font-question)] sm:text-6xl">{card.term}</p>
            {phase === 'same_day_retry' && card.retry_count > 0 && (
              <p className="mt-4 text-center text-xs text-quiet">今日已再复习 {card.retry_count} 次</p>
            )}
            <div className="mt-14 grid gap-3 sm:grid-cols-3">
              {RATING_BUTTONS.map((item) => (
                <Button key={item.value} variant={item.variant} className="h-auto min-h-16 flex-col gap-1 py-3" disabled={judge.isPending} onClick={() => judge.mutate(item.value)}>
                  <span>{judge.isPending ? '提交中…' : item.label}</span><span className="text-xs opacity-75">{item.note}</span>
                </Button>
              ))}
            </div>
            {judge.isError && <p className="mt-5 text-sm text-accent">提交失败，请重试。</p>}
            <p className="mt-5 text-center text-xs text-quiet">快捷键：1 认识 · 2 模糊 · 3 不认识</p>
          </div>
        ) : null}
      </section>
    </div>
  )
}
