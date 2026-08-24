import { useState } from 'react'
import { Link } from 'react-router-dom'
import { PATHS } from '@/lib/paths'
import { cn } from '@/lib/utils'
import type { StudyPlanDay } from '@/types/api'

/**
 * 学习计划月历：ink-10 细线网格、周一起 7 列。
 * 计划日格内放主题 + 题数；已生成试卷的整格可点进卷子，未生成的点击滚到下方 DAY 行。
 * 今天 = 日号旁橙红圆点；中考日 = 橙红细线 chip。计划全部无日期时返回 null。
 */

/** 本地时区 YYYY-MM-DD（补零拼串，不走 toISOString 免时区漂移） */
function toIso(d: Date): string {
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

/** 'YYYY-MM-DD' → 月序号（year*12+month，跨年可比较大小）；格式损坏返回 null */
function monthIndexOf(iso: string): number | null {
  const m = /^(\d{4})-(\d{2})-\d{2}$/.exec(iso)
  return m ? Number(m[1]) * 12 + (Number(m[2]) - 1) : null
}

export function StudyPlanCalendar({
  days,
  examDate,
}: {
  days: StudyPlanDay[]
  examDate: string | null
}) {
  const dated = days.filter((d): d is StudyPlanDay & { date: string } => !!d.date)
  const today = new Date()
  const todayIso = toIso(today)
  const todayMonth = today.getFullYear() * 12 + today.getMonth()

  // 计划日期 → 月序号（已滤掉 null date；格式异常的也丢弃）
  const planMonths = dated
    .map((d) => monthIndexOf(d.date))
    .filter((m): m is number => m !== null)

  // 可切月范围：[计划最早或今天, 计划最晚或中考日期] 覆盖的月份
  const examMonth = examDate ? monthIndexOf(examDate) : null
  const minMonth = Math.min(todayMonth, ...planMonths)
  const maxMonth = Math.max(todayMonth, ...planMonths, examMonth ?? -Infinity)

  // 默认月：今天所在月；计划全部在其他月时落到计划首日所在月
  const [month, setMonth] = useState(() =>
    planMonths.includes(todayMonth) || planMonths.length === 0
      ? todayMonth
      : Math.min(...planMonths),
  )

  // 健壮性：计划里没有任何可用日期就不渲染（页面层同样判断）
  if (planMonths.length === 0) return null

  const byDate = new Map(dated.map((d) => [d.date, d]))
  const year = Math.floor(month / 12)
  const month0 = month % 12

  // 周一起的月网格：补齐首尾出月格，行数按月
  const lead = (new Date(year, month0, 1).getDay() + 6) % 7
  const daysInMonth = new Date(year, month0 + 1, 0).getDate()
  const cellCount = Math.ceil((lead + daysInMonth) / 7) * 7
  const cells = Array.from(
    { length: cellCount },
    (_, i) => new Date(year, month0, 1 - lead + i),
  )

  /** 点未生成试卷的计划日：滚到下方对应 DAY 行（DayRow 有 id="day-N"） */
  const scrollToDay = (index: number) =>
    document.getElementById(`day-${index}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })

  return (
    <div>
      {/* 月份标题 + 切月 */}
      <div className="mb-3 flex items-baseline justify-between">
        <span className="font-ui text-[15px] text-ink">
          {year} 年 {month0 + 1} 月
        </span>
        <span className="flex gap-1">
          {([
            ['‹', -1, '上一月'],
            ['›', 1, '下一月'],
          ] as const).map(([glyph, delta, label]) => {
            const next = month + delta
            const disabled = next < minMonth || next > maxMonth
            return (
              <button
                key={label}
                type="button"
                aria-label={label}
                disabled={disabled}
                onClick={() => setMonth(next)}
                className="rounded-sm px-2.5 py-0.5 font-ui text-[15px] leading-none text-muted-ink transition-colors hover:bg-tint hover:text-accent disabled:pointer-events-none disabled:text-quiet/40"
              >
                {glyph}
              </button>
            )
          })}
        </span>
      </div>

      {/* 周标题（周一起） */}
      <div className="grid grid-cols-7">
        {['一', '二', '三', '四', '五', '六', '日'].map((w) => (
          <span key={w} className="px-2 pb-1.5 font-ui text-[11px] text-quiet">
            {w}
          </span>
        ))}
      </div>

      {/* 月网格：ink-10 细线 */}
      <div className="grid grid-cols-7 border-t border-l border-ink-10">
        {cells.map((date) => {
          const iso = toIso(date)
          const inMonth = date.getMonth() === month0
          const plan = inMonth ? byDate.get(iso) : undefined
          const isToday = inMonth && iso === todayIso
          const isExam = inMonth && examDate === iso

          const dayNumber = (
            <span
              className={cn(
                'flex items-center gap-1 font-ui text-[12.5px] leading-none tabular-nums',
                inMonth ? (plan ? 'text-ink' : 'text-muted-ink') : 'text-quiet/40',
              )}
            >
              {date.getDate()}
              {isToday && <span aria-hidden className="size-1.5 rounded-full bg-accent" />}
            </span>
          )

          const inner = (
            <>
              {dayNumber}
              {isExam && (
                <span className="self-start rounded-sm border border-hairline px-1 py-px font-ui text-[11px] leading-tight text-accent">
                  中考
                </span>
              )}
              {plan && (
                <>
                  <span className="truncate text-[13px] leading-snug text-ink">{plan.theme}</span>
                  <span className="flex items-center gap-1 font-ui text-[11.5px] leading-none tabular-nums text-quiet">
                    {!plan.paper_id && (
                      <span aria-hidden className="size-1.5 rounded-full bg-ink-30" />
                    )}
                    {plan.total_questions} 题
                  </span>
                </>
              )}
            </>
          )

          const cellClass = cn(
            'flex min-h-[72px] flex-col gap-1 border-r border-b border-ink-10 p-2 text-left',
            isToday && plan && 'bg-wash',
          )

          // 已生成试卷 → 整格进卷子；未生成 → 滚到下方 DAY 行；其余是纯展示格
          if (plan?.paper_id) {
            return (
              <Link
                key={iso}
                to={PATHS.paper(plan.paper_id)}
                aria-label={`${iso} ${plan.theme}`}
                className={cn(cellClass, 'transition-colors hover:bg-tint')}
              >
                {inner}
              </Link>
            )
          }
          if (plan) {
            return (
              <button
                key={iso}
                type="button"
                aria-label={`${iso} ${plan.theme}（试卷待生成）`}
                onClick={() => scrollToDay(plan.index)}
                className={cn(cellClass, 'transition-colors hover:bg-tint')}
              >
                {inner}
              </button>
            )
          }
          return (
            <div key={iso} className={cellClass}>
              {inner}
            </div>
          )
        })}
      </div>

      {/* 图例：实际样式小样 */}
      <div className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1.5 font-ui text-[11.5px] text-quiet">
        <span className="flex items-center gap-1.5">
          <span
            aria-hidden
            className="chip h-4 px-1 text-[10.5px] leading-none text-ink"
          >
            主题
          </span>
          计划日
        </span>
        <span className="flex items-center gap-1.5">
          <span aria-hidden className="size-1.5 rounded-full bg-ink-30" />
          试卷待生成
        </span>
        <span className="flex items-center gap-1.5">
          <span aria-hidden className="size-1.5 rounded-full bg-accent" />
          今天
        </span>
        <span className="flex items-center gap-1.5">
          <span
            aria-hidden
            className="rounded-sm border border-hairline px-1 py-px text-[10.5px] leading-tight text-accent"
          >
            中考
          </span>
          中考日
        </span>
      </div>
    </div>
  )
}
