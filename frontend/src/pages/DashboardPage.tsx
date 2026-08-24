import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { cn } from '@/lib/utils'
import { PageHeader } from '@/components/PageHeader'
import { PipelineProgress } from '@/components/PipelineProgress'
import { ContinueList } from '@/components/dashboard/ContinueList'
import { DailyPlan } from '@/components/dashboard/DailyPlan'
import { WeakSpots } from '@/components/dashboard/WeakSpots'
import { useAuth } from '@/hooks/useAuth'
import { useGeneratePaper } from '@/hooks/useGeneratePaper'
import { useCredits } from '@/hooks/useCredits'
import { getMastery } from '@/api/mastery'
import { listPapers } from '@/api/papers'
import { getLatestStudyPlan } from '@/api/agent'
import { getVocabularyProgress } from '@/api/vocabulary'
import { composeQuery, type ComposeInput } from '@/lib/composeQuery'
import { daysUntilExam } from '@/lib/examDate'
import { PATHS } from '@/lib/paths'
import { Button } from '@/components/ui/button'

/** 首次使用三步引导（papers 为空时替换今日计划/一练） */
const FIRST_STEPS = [
  { marker: '①', text: '选一类题型出卷' },
  { marker: '②', text: '在线作答即时判分' },
  { marker: '③', text: '逐题看 AI 讲解' },
] as const

/** 本地日期 → YYYY-MM-DD（与 StudyPlanCalendar 同款，用于匹配当天计划） */
function toIso(d: Date): string {
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

/**
 * 工作台（登录后首页）：bento 式大小不一方块（统一分科色系）。
 * 左栏 = 一句话输入 + 今日学习计划卷（大）+ 今日一练/背单词进度（中）+ 常用入口；
 * 右栏 = 弱点速览 + 继续作答。lg 以下塌成单列。
 */
export function DashboardPage() {
  const [query, setQuery] = useState('')
  const [serverError, setServerError] = useState<string | null>(null)

  const { data: user } = useAuth()
  const { total: creditsTotal, daily: creditsDaily } = useCredits()
  const { generate, isPending } = useGeneratePaper(setServerError)
  const userId = user?.id ?? 'anon'
  const examDays = daysUntilExam(userId)

  const papersQuery = useQuery({
    queryKey: ['papers', 'recent'],
    queryFn: () => listPapers(20, 0),
    staleTime: 15_000,
  })
  const masteryQuery = useQuery({
    queryKey: ['mastery', 'me', '30'],
    queryFn: () => getMastery(30),
  })
  const planQuery = useQuery({
    queryKey: ['study-plan', 'latest'],
    queryFn: getLatestStudyPlan,
    staleTime: 30_000,
  })
  const vocabQuery = useQuery({
    queryKey: ['vocabulary', 'progress'],
    queryFn: getVocabularyProgress,
    staleTime: 30_000,
  })

  /** 结构化配方出卷（今日一练/弱点专练共用）。返回 true = 已实际发起 */
  const submitCompose = (input: ComposeInput): boolean => {
    setServerError(null)
    generate({ user_query: composeQuery(input), mode: 'fresh' })
    return true
  }

  /** 一句话迷你输入条：Enter 提交（避开输入法组词态） */
  const submitFreeText = () => {
    const q = query.trim()
    if (q === '' || isPending) return
    setServerError(null)
    generate({ user_query: q, mode: 'fresh' })
  }

  const unfinished = (papersQuery.data?.items ?? []).filter((p) => !p.submitted).slice(0, 5)
  const firstUse = papersQuery.isSuccess && papersQuery.data.items.length === 0

  // 当天学习计划项（有 paper_id 才可直接进入试卷）
  const todayIso = toIso(new Date())
  const todayPlan = planQuery.data?.days.find((d) => d.date === todayIso)

  const vocab = vocabQuery.data
  const vocabPct = vocab && vocab.total_words > 0
    ? Math.round((vocab.learned_count / vocab.total_words) * 100)
    : 0

  return (
    <div className="max-w-[64rem]">
      <PageHeader title="工作台" intro={`${user?.username ?? ''}，今天练点什么？`}>
        <div className="flex flex-col items-end gap-1 text-[13px] text-quiet">
          {examDays !== null && (
            <span className="font-ui tabular-nums">距中考 {examDays} 天</span>
          )}
          {creditsTotal !== null && (
            <Link
              to={PATHS.credits}
              className={cn('font-ui tabular-nums transition-colors hover:text-accent', creditsTotal === 0 && 'text-accent')}
              title={`今日赠送剩余 ${creditsDaily ?? 0}`}
            >
              积分 {creditsTotal}{creditsDaily ? ` · 今日赠送 ${creditsDaily}` : ''} →
            </Link>
          )}
        </div>
      </PageHeader>

      <div className="lg:grid lg:grid-cols-[minmax(0,1fr)_300px] lg:gap-8">
        {/* 左栏 = bento */}
        <div className="flex min-w-0 flex-col gap-6">
          {/* 一句话出卷：红底白字大输入区，吸引主动作 */}
          <section className="dash-hero-input">
            <div className="hero-label">GENERATE · 一句话出卷</div>
            <div className="hero-row">
              <input
                type="text"
                value={query}
                disabled={isPending}
                placeholder="来 12 道现在完成时的单项选择——说需求，几秒出卷"
                className="hero-input"
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.nativeEvent.isComposing) submitFreeText()
                }}
              />
              <button
                type="button"
                disabled={isPending || !query.trim()}
                onClick={submitFreeText}
                className="hero-submit"
              >
                {isPending ? '生成中…' : '出卷 →'}
              </button>
            </div>
            <div className="hero-foot">
              <Link to={PATHS.generate} className="hero-more">展开完整版 →</Link>
              {serverError && <span className="hero-err">{serverError}</span>}
            </div>
          </section>

          {firstUse ? (
            /* 首次使用空态 */
            <section className="flex flex-col gap-4 border-t border-hairline pt-6">
              <div className="flex flex-col divide-y divide-ink-10">
                {FIRST_STEPS.map((step) => (
                  <div key={step.marker} className="flex items-baseline gap-3 px-2 py-3.5">
                    <span className="font-ui text-[14px] text-accent">{step.marker}</span>
                    <span className="text-[14.5px] text-ink">{step.text}</span>
                  </div>
                ))}
              </div>
              <Button asChild size="lg" className="self-start">
                <Link to={PATHS.practice}>去练习中心</Link>
              </Button>
            </section>
          ) : (
            <div className="bento">
              {/* 今日学习计划卷（大方块，通栏，accent）→ 直接进试卷 */}
              {todayPlan?.paper_id ? (
                <Link to={PATHS.paper(todayPlan.paper_id)} className="card col-6 is-accent">
                  <span className="card-kicker">今日学习计划 · {todayPlan.paper_title || todayPlan.theme}</span>
                  <span className="card-title">{todayPlan.theme}</span>
                  <span className="card-sub">
                    {todayPlan.kp_names.length > 0 ? todayPlan.kp_names.join(' · ') + ' · ' : ''}
                    共 {todayPlan.total_questions} 题{todayPlan.note ? ` · ${todayPlan.note}` : ''}
                  </span>
                  <span className="card-cta">开始今天这份 →</span>
                </Link>
              ) : planQuery.data ? (
                <Link to={PATHS.studyPlan} className="card col-6 is-accent">
                  <span className="card-kicker">今日学习计划</span>
                  <span className="card-title">今天暂无排定的练习</span>
                  <span className="card-sub">你的多天学习计划里今天没有安排，去看看整份计划或让助手排一份。</span>
                  <span className="card-cta">查看学习计划 →</span>
                </Link>
              ) : (
                <Link to={PATHS.assistant} className="card col-6 is-accent">
                  <span className="card-kicker">今日学习计划</span>
                  <span className="card-title">还没有学习计划</span>
                  <span className="card-sub">让 AI 学习助手按你的考试日期和薄弱环节，排一份多天计划。</span>
                  <span className="card-cta">去让助手排计划 →</span>
                </Link>
              )}

              {/* 今日一练（中方块，grammar） */}
              <div className="card col-3 is-grammar">
                <DailyPlan
                  userId={userId}
                  mastery={masteryQuery.data}
                  isPending={isPending}
                  onStart={submitCompose}
                />
              </div>

              {/* 背单词进度（中方块，listening）→ 背词进度页 */}
              <Link to={PATHS.vocabularyProgress} className="card col-3 is-listening">
                <span className="card-kicker">背单词</span>
                {vocab ? (
                  <>
                    <div className="card-stats-row">
                      <span className="card-stat">
                        <span className="n">{vocab.learned_count}</span>
                        <span className="u">/ {vocab.total_words} 已学</span>
                      </span>
                      <span className="card-stat">
                        <span className="n">{vocab.streak_days}</span>
                        <span className="u">天连续</span>
                      </span>
                    </div>
                    <div className="card-bar"><i style={{ width: `${vocabPct}%` }} /></div>
                    <span className="card-sub">
                      待复习 {vocab.due_count} · 长期掌握 {vocab.mastered_count}
                    </span>
                  </>
                ) : (
                  <span className="card-sub">国家核心 1600 词，间隔重复安排复习节奏。</span>
                )}
                <span className="card-cta">去背单词 →</span>
              </Link>
            </div>
          )}

          {isPending && <PipelineProgress />}
        </div>

        {/* 右栏 = 弱点速览 + 继续作答（也用方块） */}
        <aside className="mt-8 flex flex-col gap-4 lg:sticky lg:top-10 lg:mt-0 lg:self-start">
          <div className="card is-accent">
            <WeakSpots mastery={masteryQuery.data} isPending={isPending} onDrill={submitCompose} />
          </div>
          {unfinished.length > 0 && (
            <div className="card is-grammar">
              <ContinueList items={unfinished} />
            </div>
          )}
        </aside>
      </div>
    </div>
  )
}
