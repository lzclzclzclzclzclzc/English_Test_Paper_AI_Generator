import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { getLatestStudyPlan } from '@/api/agent'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { PageHeader } from '@/components/PageHeader'
import { StudyPlanCalendar } from '@/components/StudyPlanCalendar'
import { EmptyState } from '@/components/EmptyState'
import { useAuth } from '@/hooks/useAuth'
import { getExamDate } from '@/lib/examDate'
import { TYPE_LABELS } from '@/lib/kp'
import { PATHS } from '@/lib/paths'
import type { StudyPlanDay } from '@/types/api'

/** 学习计划单日行：细线分隔的行式列表，无卡片。 */
function DayRow({ day }: { day: StudyPlanDay }) {
  const typeLabels = [...new Set(day.question_types)]
    .map((t) => TYPE_LABELS[t] ?? t)
    .join(' / ')
  return (
    <div
      id={`day-${day.index}`}
      className="grid scroll-mt-6 grid-cols-[64px_minmax(0,1fr)_auto] items-start gap-4 border-b border-hairline py-5 max-sm:grid-cols-[minmax(0,1fr)_auto]"
    >
      {/* 第 N 天 */}
      <div className="flex flex-col max-sm:hidden">
        <span className="kicker text-accent">DAY</span>
        <span className="font-ui text-[24px] leading-tight tabular-nums text-ink">
          {String(day.index).padStart(2, '0')}
        </span>
      </div>

      <div className="flex min-w-0 flex-col gap-1.5">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          {day.theme && <span className="text-[15.5px] text-ink">{day.theme}</span>}
          <span className="font-ui text-[12.5px] tabular-nums text-quiet">
            {[typeLabels, `${day.total_questions} 道`, day.date].filter(Boolean).join(' · ')}
          </span>
        </div>
        {day.kp_names.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {day.kp_names.map((name, i) => (
              <span
                key={i}
                className="chip"
              >
                {name}
              </span>
            ))}
          </div>
        )}
        {day.note && <p className="text-[12.5px] leading-relaxed text-quiet">{day.note}</p>}
      </div>

      <Button asChild size="sm" variant="outline" className="mt-1 shrink-0">
        <Link to={PATHS.paper(day.paper_id)}>开始练习 →</Link>
      </Button>
    </div>
  )
}

/** 学习计划（dev 新功能）：按天打卡，每天一份针对性练习。 */
export function StudyPlanPage() {
  const { data: user } = useAuth()
  const userId = user?.id ?? 'anon'
  const { data: plan, isLoading, isError } = useQuery({
    queryKey: ['study-plan', 'latest'],
    queryFn: getLatestStudyPlan,
    staleTime: 30_000,
  })

  return (
    <div className="max-w-[52rem]">
      <PageHeader
        title="学习计划"
        intro="计划由学习助手制定，这里按日历跟进——去助手说出目标，AI 按天拆成打卡计划，每天一份针对性练习。"
      />

      {isLoading && (
        <div className="flex flex-col gap-3">
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      )}

      {isError && (
        <div className="flex flex-col items-start gap-3 border-t border-hairline pt-8">
          <p className="text-[13.5px] text-muted-ink">学习计划加载失败，请刷新页面重试</p>
        </div>
      )}

      {!isLoading && !isError && !plan && (
        <EmptyState
          title="还没有学习计划"
          desc="去学习助手告诉我你的目标（比如「帮我制定 7 天学习计划」），我来安排每天练什么"
          action={
            <Button asChild>
              <Link to={PATHS.assistant} state={{ prefill: '帮我制定一个 7 天学习计划' }}>
                让学习助手帮我制定计划
              </Link>
            </Button>
          }
        />
        )}

      {plan && (
        <div className="flex flex-col gap-4">
          {plan.days.some((d) => d.date) && (
            <div className="border-b border-hairline pb-6">
              <StudyPlanCalendar days={plan.days} examDate={getExamDate(userId)} />
            </div>
          )}
          <div className="flex items-baseline justify-between border-b border-hairline pb-2.5">
            <span className="text-[13px] text-muted-ink">
              共 <b className="text-ink">{plan.total_days}</b> 天
              {plan.days[0]?.date && (
                <>
                  ，从 <b className="text-ink">{plan.days[0].date}</b> 开始
                </>
              )}
            </span>
            <span className="text-[12px] text-quiet">点「开始练习」进入当天的卷子</span>
          </div>
          <div className="flex flex-col">
            {plan.days.map((day) => (
              <DayRow key={day.index} day={day} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
