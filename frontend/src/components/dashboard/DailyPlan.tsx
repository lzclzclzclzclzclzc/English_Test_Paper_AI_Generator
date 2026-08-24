import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useKnowledgePoints } from '@/hooks/useKnowledgePoints'
import type { ComposeInput } from '@/lib/composeQuery'
import { dailyDoneKey, recipeTotal, resolveRecipe, structureOf } from '@/lib/dailyRecipes'
import { PATHS } from '@/lib/paths'
import type { MasteryProfile } from '@/types/api'
import { Button } from '@/components/ui/button'

interface DailyPlanProps {
  userId: string
  mastery: MasteryProfile | undefined
  isPending: boolean
  /** 返回 true = 已实际发起生成；false = 被余额预检拦截 */
  onStart: (input: ComposeInput) => boolean
}

/**
 * 今日一练：按星期轮换的固定配方一键出卷。配方与「练过」标记的事实
 * 来源在 `lib/dailyRecipes.ts`（与 /daily 每日一练页共用）——键存在即
 * 视为练过（不存 paper_id，不做打卡链），仍可「再练一组」。
 */
export function DailyPlan({ userId, mastery, isPending, onStart }: DailyPlanProps) {
  const kpQuery = useKnowledgePoints()
  const [, setTick] = useState(0)

  const todayKey = dailyDoneKey(userId)
  const doneToday = localStorage.getItem(todayKey) !== null

  const recipe = resolveRecipe(new Date().getDay(), mastery, kpQuery.data)
  const total = recipeTotal(recipe)

  const start = () => {
    const started = onStart({ entries: recipe.entries })
    if (started) {
      localStorage.setItem(todayKey, 'pending')
      setTick((t) => t + 1)
    }
  }

  return (
    <section className="flex flex-col gap-3">
      <span className="kicker">
        今日一练 · {recipe.name}
      </span>
      <p className="text-[13.5px] leading-relaxed text-muted-ink">
        {structureOf(recipe.entries)} · 共 {total} 题 · 约 {recipe.minutes} 分钟
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
      <Link
        to={PATHS.daily}
        className="self-start font-ui text-[13px] text-quiet transition-colors hover:text-accent"
      >
        查看一周安排 →
      </Link>
    </section>
  )
}
