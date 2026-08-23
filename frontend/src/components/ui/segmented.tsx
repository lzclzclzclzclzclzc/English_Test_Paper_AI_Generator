import { cn } from '@/lib/utils'

export interface SegmentedOption<T extends string | number> {
  value: T
  label: React.ReactNode
  disabled?: boolean
}

interface SegmentedProps<T extends string | number> {
  value: T
  onChange: (value: T) => void
  options: readonly SegmentedOption<T>[]
  /** default = h-8 / 13px；sm = h-7 / 12.5px（紧凑筛选条） */
  size?: 'default' | 'sm'
  /** 视觉无障碍名（radiogroup） */
  'aria-label'?: string
  className?: string
  disabled?: boolean
}

/**
 * 分段选择（卷王 variant-5）：一排方角按钮，选中态 = 墨色实心（深墨底 + 纸色字）。
 * 样式走 index.css 的 .seg / .seg-sm；本组件只管 aria-pressed 与 onChange。
 * 凡是"单选一个离散值"的地方（时间窗、出题方式、限时、题量、主题）都用它，
 * 不再手写 border-accent bg-wash。
 */
export function Segmented<T extends string | number>({
  value,
  onChange,
  options,
  size = 'default',
  className,
  disabled,
  ...rest
}: SegmentedProps<T>) {
  return (
    <div role="group" aria-label={rest['aria-label']} className={cn('flex flex-wrap gap-2', className)}>
      {options.map((opt) => (
        <button
          key={String(opt.value)}
          type="button"
          aria-pressed={opt.value === value}
          disabled={disabled || opt.disabled}
          onClick={() => onChange(opt.value)}
          className={cn('seg', size === 'sm' && 'seg-sm')}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}
