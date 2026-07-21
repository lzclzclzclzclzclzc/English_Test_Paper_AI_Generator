import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { BookOpen, Calendar, CheckCircle2 } from 'lucide-react'
import { getLatestStudyPlan } from '@/api/agent'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import type { StudyPlanDay } from '@/types/api'

const TYPE_LABEL: Record<string, string> = {
  single_choice: '单选题',
  word_form: '词性转换',
  sentence_rewriting: '改写句子',
}

function DayCard({ day }: { day: StudyPlanDay }) {
  return (
    <div className="flex items-center gap-4 rounded-lg border border-line bg-sheet px-4 py-3">
      {/* 序号 */}
      <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-ink text-[13px] font-bold text-paper">
        {day.index}
      </div>

      {/* 内容 */}
      <div className="flex flex-1 flex-col gap-0.5 overflow-hidden">
        <div className="flex items-center gap-2">
          <span className="text-[13.5px] font-medium text-foreground">{day.kp_name}</span>
          <span className="rounded-full bg-ink-wash px-2 py-0.5 text-[11px] text-text-mid">
            {TYPE_LABEL[day.question_type] ?? day.question_type}
          </span>
          <span className="text-[12px] text-text-mid">{day.count} 道</span>
        </div>
        <div className="flex items-center gap-2 text-[12px] text-text-mid">
          {day.date && (
            <>
              <Calendar className="size-3" />
              <span>{day.date}</span>
            </>
          )}
          {day.note && <span className="truncate">{day.note}</span>}
        </div>
      </div>

      {/* 操作 */}
      <Button asChild size="sm" variant="outline" className="shrink-0 text-xs">
        <Link to={`/papers/${day.paper_id}`}>开始练习 →</Link>
      </Button>
    </div>
  )
}

export function StudyPlanPage() {
  const { data: plan, isLoading, isError } = useQuery({
    queryKey: ['study-plan', 'latest'],
    queryFn: getLatestStudyPlan,
    staleTime: 30_000,
  })

  return (
    <div className="mx-auto max-w-[720px] px-6 pt-12">
      <div className="mb-8 flex flex-col gap-1">
        <h1 className="font-serif text-2xl font-bold text-foreground">我的学习计划</h1>
        <p className="text-[13.5px] text-text-mid">按天打卡，每天完成一份针对性练习</p>
      </div>

      {isLoading && (
        <div className="flex flex-col gap-3">
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-16 w-full rounded-lg" />
          ))}
        </div>
      )}

      {isError && (
        <div className="rounded-lg border border-line bg-sheet px-4 py-8 text-center text-[13.5px] text-text-mid">
          加载失败，请刷新页面重试
        </div>
      )}

      {!isLoading && !isError && !plan && (
        <div className="flex flex-col items-center gap-4 rounded-lg border border-line bg-sheet px-6 py-12 text-center">
          <BookOpen className="size-10 text-text-mid" strokeWidth={1.5} />
          <div className="flex flex-col gap-1">
            <p className="text-[14px] font-medium text-foreground">还没有学习计划</p>
            <p className="text-[13px] text-text-mid">
              去
              <Link to="/" className="mx-1 text-ink underline underline-offset-2">
                学习助手
              </Link>
              告诉我你的目标，我来制定计划
            </p>
          </div>
        </div>
      )}

      {plan && (
        <div className="flex flex-col gap-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[13px] text-text-mid">
              共 <span className="font-medium text-foreground">{plan.total_days}</span> 天
              {plan.days[0]?.date && (
                <>，从 <span className="font-medium text-foreground">{plan.days[0].date}</span> 开始</>
              )}
            </span>
            <div className="flex items-center gap-1.5 text-[12px] text-text-mid">
              <CheckCircle2 className="size-3.5 text-green-500" />
              <span>点击「开始练习」进入做题页</span>
            </div>
          </div>

          {plan.days.map((day) => (
            <DayCard key={day.index} day={day} />
          ))}
        </div>
      )}
    </div>
  )
}
