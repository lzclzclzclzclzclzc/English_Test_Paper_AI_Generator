import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getMastery } from '@/api/mastery'
import { useAuth } from '@/hooks/useAuth'
import { useGeneratePaper } from '@/hooks/useGeneratePaper'
import { useKnowledgePoints } from '@/hooks/useKnowledgePoints'
import { PageHeader } from '@/components/PageHeader'
import { PipelineProgress } from '@/components/PipelineProgress'
import { CreditHint } from '@/components/CreditHint'
import { composeQuery } from '@/lib/composeQuery'
import {
  SUNDAY_NAME,
  WEEKDAYS,
  dailyDoneKey,
  recipeTotal,
  resolveRecipe,
  structureOf,
} from '@/lib/dailyRecipes'
import { useCredits } from '@/hooks/useCredits'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'

/**
 * 每日一练页：今日配方一键出卷 + 一周安排表。
 * 配方数据与解析逻辑全在 lib/dailyRecipes.ts(与工作台「今日一练」卡共用);
 * 出卷范式同 MockPage(本地预估价 guard → generate;余额不足由 402 弹充值)。
 */
export function DailyPage() {
  const [serverError, setServerError] = useState<string | null>(null)
  // 「今天已练过」标记写入后 bump 重渲染(localStorage 非响应式)
  const [, setTick] = useState(0)

  const { data: user } = useAuth()
  const userId = user?.id ?? 'anon'
  const { generate, guard, isPending } = useGeneratePaper(setServerError)
  const { price } = useCredits()

  const masteryQuery = useQuery({
    queryKey: ['mastery', 'me', '30'],
    queryFn: () => getMastery(30),
  })
  const kpQuery = useKnowledgePoints()

  const todayDay = new Date().getDay()
  const todayLabel = WEEKDAYS.find((w) => w.day === todayDay)?.label ?? ''
  const todayRecipe = resolveRecipe(todayDay, masteryQuery.data, kpQuery.data)
  const doneToday = localStorage.getItem(dailyDoneKey(userId)) !== null
  // 每日一练默认 AI 改编强度
  const estimatedCost = price('generate_light', recipeTotal(todayRecipe))

  // 周日弱点日:能按掌握度解析出动态配方时展示实际组合,否则给引导句
  const sundayRecipe = resolveRecipe(0, masteryQuery.data, kpQuery.data)
  const sundayDynamic = sundayRecipe.name === SUNDAY_NAME

  const start = () => {
    setServerError(null)
    if (!guard(estimatedCost)) return
    localStorage.setItem(dailyDoneKey(userId), 'pending')
    setTick((t) => t + 1)
    generate({ user_query: composeQuery({ entries: todayRecipe.entries }), mode: 'fresh' })
  }

  return (
    <div className="max-w-[56rem]">
      <PageHeader
        title="每日一练"
        intro="每天一组小卷，配方按星期轮换——不用想练什么，打开就开始。"
      />

      <div className="flex flex-col gap-10">
        {/* 今日卡区 */}
        <section className="flex flex-col gap-3 border-t border-hairline pt-6">
          <span className="kicker">
            今日 · {todayLabel} · {todayRecipe.name}
          </span>
          <p className="text-[13.5px] leading-relaxed text-muted-ink">
            {structureOf(todayRecipe.entries)} · 共 {recipeTotal(todayRecipe)} 题 · 约{' '}
            {todayRecipe.minutes} 分钟
          </p>
          <div>
            {doneToday ? (
              <Button
                variant="outline"
                size="lg"
                type="button"
                disabled={isPending}
                onClick={start}
              >
                {isPending ? '生成中…' : '今天已练过 · 再练一组'}
              </Button>
            ) : (
              <Button
                size="lg"
                type="button"
                disabled={isPending}
                onClick={start}
              >
                {isPending ? '生成中…' : '开始今日一练'}
              </Button>
            )}
          </div>
          <CreditHint action="generate_light" cost={estimatedCost} prefix="约" />
          {serverError && <p className="text-[12px] text-accent">{serverError}</p>}
        </section>

        {isPending && <PipelineProgress />}

        {/* 一周安排表 */}
        <section className="flex flex-col gap-3 border-t border-hairline pt-6">
          <span className="kicker">
            一周安排
          </span>
          <div className="divide-y divide-ink-10 border-y border-hairline">
            {WEEKDAYS.map(({ day, label }) => {
              const isSunday = day === 0
              const recipe = isSunday ? sundayRecipe : resolveRecipe(day, undefined, undefined)
              const name = isSunday ? SUNDAY_NAME : recipe.name
              const summary =
                isSunday && !sundayDynamic
                  ? '按你的薄弱考点动态组卷（需先有答题记录）'
                  : structureOf(recipe.entries)
              return (
                <div
                  key={day}
                  className={cn(
                    'flex flex-wrap items-baseline gap-x-4 gap-y-1 border-l-2 px-3 py-3.5',
                    day === todayDay ? 'border-accent bg-tint' : 'border-transparent',
                  )}
                >
                  <span className="w-10 shrink-0 font-ui text-[13px] text-ink">{label}</span>
                  <span className="shrink-0 text-[14px] text-ink">{name}</span>
                  <span className="min-w-0 flex-1 basis-[16rem] text-[13px] leading-relaxed text-quiet">
                    {summary}
                  </span>
                  <span className="ml-auto shrink-0 font-ui text-[12.5px] tabular-nums text-quiet">
                    约 {recipe.minutes} 分钟
                  </span>
                </div>
              )
            })}
          </div>
        </section>

        <p className="text-[12.5px] text-quiet">
          每日一练按 AI 改编价计积分；每天赠送的免费积分正好够练一组小卷。
        </p>
      </div>
    </div>
  )
}
