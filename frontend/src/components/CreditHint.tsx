import { useCredits } from '@/hooks/useCredits'
import { cn } from '@/lib/utils'
import type { CreditAction } from '@/types/payment'

interface CreditHintProps {
  action: CreditAction | string
  /** 题数 / 篇数（按次计价的动作不传） */
  units?: number
  /** 直接给定费用（已在外部算好时） */
  cost?: number | null
  prefix?: string
  className?: string
}

/**
 * CTA 旁的「≈ N 积分」小字：价格来自 useCredits().priceTable，余额不够时转橙红。
 * 价目表未加载时不渲染（不显示 0）。
 */
export function CreditHint({ action, units = 0, cost, prefix = '≈', className }: CreditHintProps) {
  const { price, canAfford } = useCredits()
  const value = cost === undefined ? price(action, units) : cost
  if (value === null) return null
  const short = !canAfford(value)
  return (
    <span
      className={cn('font-ui text-[12px] tabular-nums', short ? 'text-accent' : 'text-quiet', className)}
      title={short ? '积分不足，点击按钮会提示充值' : undefined}
    >
      {prefix} {value} 积分
    </span>
  )
}
