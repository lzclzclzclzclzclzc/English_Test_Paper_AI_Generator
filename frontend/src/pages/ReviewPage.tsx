import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getReadiness } from '@/api/health'
import { useAuth } from '@/hooks/useAuth'
import { useGeneratePaper } from '@/hooks/useGeneratePaper'
import { loadWrongBook, removeEntry, toWrongItemRefs, type WrongBookEntry } from '@/lib/wrongBook'
import { stopAll as stopTTS } from '@/lib/tts'
import { PageHeader } from '@/components/PageHeader'
import { ReviewGeneratePanel } from '@/components/review/ReviewGeneratePanel'
import { WrongBookList } from '@/components/review/WrongBookList'
import { UpgradeDialog } from '@/components/UpgradeDialog'

/** 错题复习：错题巩固 / 综合复习两个出卷入口 + 本地错题本。 */
export function ReviewPage() {
  const { data: user } = useAuth()
  const userId = user?.id ?? 'anon'

  const [entries, setEntries] = useState<WrongBookEntry[]>([])
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [serverError, setServerError] = useState<string | null>(null)
  const [upgradeReason, setUpgradeReason] = useState<string | null>(null)

  // 用户加载后读错题本，默认全选
  useEffect(() => {
    if (!user?.id) return
    const loaded = loadWrongBook(user.id)
    setEntries(loaded)
    setSelected(new Set(loaded.map((e) => e.sourceQuestionId)))
  }, [user?.id])

  // 离开错题本页面时停止所有 TTS 播放
  useEffect(() => () => stopTTS(), [])

  const { generate, guard, isPending, locked } = useGeneratePaper(setServerError)

  const readiness = useQuery({
    queryKey: ['health', 'ready'],
    queryFn: getReadiness,
    staleTime: 60_000,
    retry: false,
    refetchOnWindowFocus: false,
  })

  const toggle = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  const toggleAll = () =>
    setSelected((prev) =>
      prev.size === entries.length
        ? new Set()
        : new Set(entries.map((e) => e.sourceQuestionId)),
    )

  const remove = (id: string) => {
    setEntries(removeEntry(userId, id))
    setSelected((prev) => {
      const next = new Set(prev)
      next.delete(id)
      return next
    })
  }

  const submitRemediation = (extraQuery: string) => {
    setServerError(null)
    const reason = guard('remediation')
    if (reason) {
      setUpgradeReason(reason)
      return
    }
    const chosen = entries.filter((e) => selected.has(e.sourceQuestionId))
    generate({
      user_query: extraQuery || '针对我错题本里的这些题目，出一份巩固练习',
      mode: 'remediation',
      wrong_items: toWrongItemRefs(chosen),
    })
  }

  const submitReview = (windowDays: number) => {
    setServerError(null)
    const reason = guard('review')
    if (reason) {
      setUpgradeReason(reason)
      return
    }
    // 文案保持朴素：带"最近 N 天"等场景语义会触发向量检索（需本机 embedding 模型）；
    // 统计窗口走 review_window_days 参数即可
    generate({
      user_query: '出一份综合复习卷',
      mode: 'review',
      review_window_days: windowDays,
    })
  }

  return (
    <div className="flex max-w-[56rem] flex-col gap-8">
      <PageHeader
        title="错题本"
        intro="答错的题都收在错题本里，可以定向巩固，也可以让 AI 按薄弱考点出复习卷。"
      />

      {readiness.data?.status === 'not_ready' && (
        <div className="max-w-[44rem] border-t border-accent pt-2.5 text-[13px] text-muted-ink">
          题库正在准备中，出卷可能暂时失败，可以稍后再试
        </div>
      )}

      <ReviewGeneratePanel
        locked={locked}
        isPending={isPending}
        wrongTotal={entries.length}
        selectedCount={selected.size}
        onRemediate={submitRemediation}
        onReview={submitReview}
        serverError={serverError}
      />

      <WrongBookList
        entries={entries}
        selected={selected}
        onToggle={toggle}
        onToggleAll={toggleAll}
        onRemove={remove}
        locked={locked}
        userId={userId}
      />

      <UpgradeDialog reason={upgradeReason} onClose={() => setUpgradeReason(null)} />
    </div>
  )
}
