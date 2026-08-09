import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { cn } from '@/lib/utils'
import { PageHeader } from '@/components/PageHeader'
import { PipelineProgress } from '@/components/PipelineProgress'
import { UpgradeDialog } from '@/components/UpgradeDialog'
import { ContinueList } from '@/components/dashboard/ContinueList'
import { DailyPlan } from '@/components/dashboard/DailyPlan'
import { WeakSpots } from '@/components/dashboard/WeakSpots'
import { useAuth } from '@/hooks/useAuth'
import { useGeneratePaper } from '@/hooks/useGeneratePaper'
import { useMembership } from '@/hooks/useMembership'
import { getMastery } from '@/api/mastery'
import { listPapers } from '@/api/papers'
import { composeQuery, type ComposeInput } from '@/lib/composeQuery'
import { daysUntilExam } from '@/lib/examDate'
import { PATHS } from '@/lib/paths'
import { FREE_GENERATE_PER_DAY, generateQuotaNotice } from '@/lib/quota'

/** 右栏「常用」竖排链接 */
const SHORTCUTS = [
  { to: PATHS.practice, title: '练习中心', desc: '九大题型，逐类专项练习' },
  { to: PATHS.mock, title: '整卷模拟', desc: '一键出一份完整检测卷' },
  { to: PATHS.review, title: '错题本', desc: '错过的题，再练到会' },
] as const

/** 首次使用三步引导（papers 为空时替换左栏「今日一练/继续作答」） */
const FIRST_STEPS = [
  { marker: '①', text: '选一类题型出卷' },
  { marker: '②', text: '在线作答即时判分' },
  { marker: '③', text: '逐题看 AI 讲解' },
] as const

/**
 * 工作台（登录后首页）：双栏——左栏行动流（一句话迷你输入条 +
 * 今日一练 + 继续作答），右栏粘顶信息栏（弱点速览 / 常用 / 词汇预告，
 * 细线分段不做卡）。lg 以下塌成单列，右栏内容置底。
 */
export function DashboardPage() {
  const [query, setQuery] = useState('')
  const [serverError, setServerError] = useState<string | null>(null)
  const [upgradeReason, setUpgradeReason] = useState<string | null>(null)

  const { data: user } = useAuth()
  const { isMember } = useMembership()
  const { generate, guard, isPending, locked, freeRemaining } = useGeneratePaper(setServerError)
  const userId = user?.id ?? 'anon'
  const examDays = daysUntilExam(userId)
  const quotaNotice = generateQuotaNotice(locked, freeRemaining)

  const papersQuery = useQuery({
    queryKey: ['papers', 'recent'],
    queryFn: () => listPapers(20, 0),
    staleTime: 15_000,
  })
  const masteryQuery = useQuery({
    queryKey: ['mastery', 'me', '30'],
    queryFn: () => getMastery(30),
  })

  /** 结构化配方出卷（今日一练/弱点专练共用）。返回 true = 已实际发起 */
  const submitCompose = (input: ComposeInput): boolean => {
    setServerError(null)
    const reason = guard('fresh')
    if (reason) {
      setUpgradeReason(reason)
      return false
    }
    generate({ user_query: composeQuery(input), mode: 'fresh' })
    return true
  }

  /** 一句话迷你输入条：Enter 提交（避开输入法组词态） */
  const submitFreeText = () => {
    const q = query.trim()
    if (q === '' || isPending) return
    setServerError(null)
    const reason = guard('fresh')
    if (reason) {
      setUpgradeReason(reason)
      return
    }
    generate({ user_query: q, mode: 'fresh' })
  }

  const unfinished = (papersQuery.data?.items ?? []).filter((p) => !p.submitted).slice(0, 2)
  const firstUse = papersQuery.isSuccess && papersQuery.data.items.length === 0

  return (
    <div className="max-w-[64rem]">
      <PageHeader
        title="工作台"
        intro={`${user?.username ?? ''}，今天练点什么？`}
      >
        <div className="flex flex-col items-end gap-1 text-[13px] text-quiet">
          {examDays !== null && (
            <span className="font-ui tabular-nums">距中考 {examDays} 天</span>
          )}
          {isMember ? (
            <span className="font-ui">会员 · 出卷不限次</span>
          ) : locked ? (
            <span
              className={cn('font-ui tabular-nums', freeRemaining === 0 && 'text-accent')}
            >
              今日免费出卷 {freeRemaining}/{FREE_GENERATE_PER_DAY}
            </span>
          ) : null}
        </div>
      </PageHeader>

      <div className="lg:grid lg:grid-cols-[minmax(0,1fr)_300px] lg:gap-12">
        {/* 左栏 = 行动流：输入条 → 今日一练 → 继续作答 */}
        <div className="flex min-w-0 flex-col gap-10">
          {/* 一句话迷你输入条：Enter 出卷，右端去完整版 */}
          <section className="flex flex-col gap-2">
            <div className="flex items-center gap-5">
              <input
                type="text"
                value={query}
                disabled={isPending}
                placeholder="来 12 道现在完成时的单项选择——一句话出卷"
                className="w-full max-w-[36rem] rounded-[3px] border border-ink-20 bg-transparent px-4 py-2.5 text-[15px] text-ink outline-none transition-colors placeholder:text-quiet focus:border-accent disabled:opacity-60"
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.nativeEvent.isComposing) submitFreeText()
                }}
              />
              <Link
                to={PATHS.generate}
                className="shrink-0 font-ui text-[13px] text-quiet transition-colors hover:text-accent"
              >
                展开完整版 →
              </Link>
            </div>
            {serverError && <p className="text-[12px] text-accent">{serverError}</p>}
            {quotaNotice && (
              <p className="font-ui text-[12px] tabular-nums text-quiet">{quotaNotice}</p>
            )}
          </section>

          {firstUse ? (
            /* 首次使用空态：三步引导替换「今日一练/继续作答」，右栏照常 */
            <section className="flex flex-col gap-4 border-t border-hairline pt-6">
              <div className="flex flex-col divide-y divide-ink-10">
                {FIRST_STEPS.map((step) => (
                  <div key={step.marker} className="flex items-baseline gap-3 px-2 py-3.5">
                    <span className="font-ui text-[14px] text-accent">{step.marker}</span>
                    <span className="text-[14.5px] text-ink">{step.text}</span>
                  </div>
                ))}
              </div>
              <div>
                <Link
                  to={PATHS.practice}
                  className="inline-block rounded-sm border border-accent bg-wash px-6 py-2 font-ui text-[13.5px] tracking-[0.05em] text-ink transition-colors hover:text-accent"
                >
                  去练习中心
                </Link>
              </div>
            </section>
          ) : (
            <>
              <DailyPlan
                userId={userId}
                mastery={masteryQuery.data}
                isPending={isPending}
                onStart={submitCompose}
              />

              {unfinished.length > 0 && <ContinueList items={unfinished} />}
            </>
          )}

          {isPending && <PipelineProgress />}
        </div>

        {/* 右栏 = 粘顶信息栏：弱点速览 / 常用 / 词汇预告，细线分段不做卡 */}
        <aside className="mt-12 border-t border-hairline pt-8 lg:sticky lg:top-10 lg:mt-0 lg:self-start lg:border-t-0 lg:pt-0">
          <div className="flex flex-col divide-y divide-ink-10">
            <WeakSpots
              mastery={masteryQuery.data}
              isPending={isPending}
              onDrill={submitCompose}
            />

            {/* 常用：竖排链接列表 */}
            <section className="flex flex-col gap-2 py-5">
              <span className="font-ui text-[11px] font-bold tracking-[0.14em] text-quiet">
                常用
              </span>
              <div className="flex flex-col">
                {SHORTCUTS.map((s) => (
                  <Link
                    key={s.to}
                    to={s.to}
                    className="flex flex-col gap-0.5 rounded-sm px-2 py-2.5 transition-colors hover:bg-tint"
                  >
                    <span className="font-ui text-[14px] text-ink">{s.title}</span>
                    <span className="text-[12px] text-quiet">{s.desc}</span>
                  </Link>
                ))}
              </div>
            </section>

            {/* 词汇预告：一行带过 */}
            <p className="px-2 pt-5 text-[12.5px] leading-[1.8] text-quiet">
              词汇学习 · 即将上线 — 国家核心 1600 词，间隔重复安排复习节奏
            </p>
          </div>
        </aside>
      </div>

      <UpgradeDialog reason={upgradeReason} onClose={() => setUpgradeReason(null)} />
    </div>
  )
}
