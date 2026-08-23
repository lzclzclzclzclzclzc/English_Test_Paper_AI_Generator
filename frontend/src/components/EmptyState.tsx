import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface EmptyStateProps {
  title: string
  desc?: ReactNode
  /** 通常是一个 <Button> / <Button asChild><Link/></Button> */
  action?: ReactNode
  /** compact = 嵌在卡片/侧栏里的小空态（无顶部细线，字号更小） */
  compact?: boolean
  className?: string
}

/**
 * 空态（教学式）：一句标题 + 一句下一步 + 至多一个动作。
 * 全站统一这一种写法：左对齐、顶部细线、不画插图。
 */
export function EmptyState({ title, desc, action, compact, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-start gap-2',
        compact ? 'py-2' : 'border-t border-hairline pt-8',
        className,
      )}
    >
      <p className={cn('text-ink', compact ? 'text-[15px]' : 'text-[17px]')}>{title}</p>
      {desc && <p className="text-[13.5px] text-muted-ink">{desc}</p>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  )
}
