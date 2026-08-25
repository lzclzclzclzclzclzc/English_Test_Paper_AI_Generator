import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getReadiness } from '@/api/health'
import { useAuth } from '@/hooks/useAuth'
import { useGeneratePaper } from '@/hooks/useGeneratePaper'
import { loadWrongBook, removeEntry, toWrongItemRefs, type WrongBookEntry } from '@/lib/wrongBook'
import { stopAll as stopTTS } from '@/lib/tts'
import { PageHeader } from '@/components/PageHeader'
import { PipelineProgress } from '@/components/PipelineProgress'
import { WrongBookList } from '@/components/review/WrongBookList'
import { CreditHint } from '@/components/CreditHint'
import { Button } from '@/components/ui/button'

/**
 * 错题本页（单一职责）：错题的浏览与重练。
 * 左列 = 过滤芯片 + 错题列表；右栏粘顶「错题巩固」操作卡（mode remediation）。
 * 综合复习入口已迁往掌握度页（2026-08-07 复盘域拆分）。
 */
export function ReviewPage() {
  const { data: user } = useAuth()
  const userId = user?.id ?? 'anon'

  const [entries, setEntries] = useState<WrongBookEntry[]>([])
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [extraQuery, setExtraQuery] = useState('')
  const [serverError, setServerError] = useState<string | null>(null)

  // 用户加载后读错题本，默认全选
  useEffect(() => {
    if (!user?.id) return
    const loaded = loadWrongBook(user.id)
    setEntries(loaded)
    setSelected(new Set(loaded.map((e) => e.sourceQuestionId)))
  }, [user?.id])

  // 离开错题本页面时停止所有 TTS 播放
  useEffect(() => () => stopTTS(), [])

  const { generate, isPending } = useGeneratePaper(setServerError, 'errorbook')

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

  const selectMany = (ids: string[]) => setSelected((prev) => new Set([...prev, ...ids]))

  const clearSelection = () => setSelected(new Set())

  const remove = (id: string) => {
    setEntries(removeEntry(userId, id))
    setSelected((prev) => {
      const next = new Set(prev)
      next.delete(id)
      return next
    })
  }

  const submitRemediation = () => {
    setServerError(null)
    const chosen = entries.filter((e) => selected.has(e.sourceQuestionId))
    generate({
      user_query: extraQuery.trim() || '针对我错题本里的这些题目，出一份巩固练习',
      mode: 'remediation',
      wrong_items: toWrongItemRefs(chosen),
    })
  }

  return (
    <div className="max-w-[64rem]">
      <PageHeader
        title="错题本"
        intro="答错的题都收在这里，勾选后可以让 AI 围绕同样的考点重新出一份巩固卷。"
      >
        <span className="font-ui text-[12.5px] tabular-nums text-quiet">
          共 {entries.length} 道 · 保存在本浏览器
        </span>
      </PageHeader>

      {readiness.data?.status === 'not_ready' && (
        <div className="mb-8 max-w-[44rem] border-t border-accent pt-2.5 text-[13px] text-muted-ink">
          题库正在准备中，出卷可能暂时失败，可以稍后再试
        </div>
      )}

      <div className="lg:grid lg:grid-cols-[minmax(0,1fr)_300px] lg:gap-10">
        {/* 右栏粘顶操作卡（max-lg 置于列表上方） */}
        <aside className="mb-10 lg:order-2 lg:sticky lg:top-10 lg:mb-0 lg:self-start">
          <div className="flex flex-col gap-4 rounded-md border border-hairline p-5">
            <div className="flex items-center gap-2">
              <span className="kicker">
                错题巩固
              </span>
              <CreditHint action="generate_fresh" units={selected.size} prefix={`${selected.size} 题约`} />
            </div>

            <p className="text-[13px] leading-[1.8] text-quiet">
              AI 会围绕勾选错题的考点出全新的题，不是原题重做。
            </p>

            <p className="font-ui text-[15px] font-bold tabular-nums text-ink">
              已选 {selected.size} / 共 {entries.length} 道
            </p>

            {/* name/autoComplete/data-1p-ignore：阻止密码管理器把它当登录框弹填充 */}
            <input
              type="text"
              name="remediation-note"
              autoComplete="off"
              data-1p-ignore
              data-lpignore="true"
              value={extraQuery}
              maxLength={2000}
              placeholder="补充要求（可选），如：多出几道选择题"
              onChange={(e) => setExtraQuery(e.target.value)}
              className="w-full rounded-sm border border-ink-20 bg-transparent px-3 py-2 text-[14px] text-ink outline-none transition-colors placeholder:text-quiet focus:border-accent"
            />

            <div className="flex flex-col gap-2">
              <Button
                size="lg"
                type="button"
                disabled={selected.size === 0 || isPending}
                title={entries.length === 0 ? '交卷后答错的题会自动收进错题本' : undefined}
                onClick={submitRemediation}
              >
                {isPending ? '正在组卷…' : '生成巩固卷'}
              </Button>
              {serverError && <p className="text-[12px] text-accent">{serverError}</p>}
              <p className="font-ui text-[12px] tabular-nums text-quiet">
                已选 {selected.size} 道错题
              </p>
            </div>
          </div>
        </aside>

        {/* 左列：错题列表 */}
        <div className="min-w-0 lg:order-1">
          <WrongBookList
            entries={entries}
            selected={selected}
            onToggle={toggle}
            onSelectMany={selectMany}
            onClearSelection={clearSelection}
            onRemove={remove}
          />
        </div>
      </div>

      {isPending && (
        <div className="mt-10">
          <PipelineProgress />
        </div>
      )}
    </div>
  )
}
