import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface StatTileProps {
  label: string
  value: ReactNode
  /** 数字后的小单位（道 / 个 / 天） */
  unit?: string
  className?: string
}

/**
 * 统计小方块（卷王 variant-5）：细线边 + 卡底 + kicker + 大数字，
 * 与工作台 .bento .card-stat 同规格；用于背词进度、学情报告等一排数字。
 */
export function StatTile({ label, value, unit, className }: StatTileProps) {
  return (
    <div className={cn('flex flex-col gap-2 border border-hairline bg-card-surface px-4 py-4', className)}>
      <span className="kicker">{label}</span>
      <span className="flex items-baseline gap-1.5 text-ink">
        <span className="text-[26px] font-bold leading-none tracking-[-0.02em] tabular-nums">{value}</span>
        {unit && <span className="text-[13px] text-quiet">{unit}</span>}
      </span>
    </div>
  )
}
