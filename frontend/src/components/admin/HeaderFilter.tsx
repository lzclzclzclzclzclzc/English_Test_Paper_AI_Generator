import type { ReactNode } from 'react'
import { ListFilter } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Popover, PopoverClose, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { cn } from '@/lib/utils'

const dateInputClass =
  'mt-1 block h-8 w-full rounded-md border border-hairline bg-transparent px-2 text-[13px] text-ink outline-none focus-visible:border-ring'

/**
 * 表头右侧的筛选漏斗：命中筛选时变赤陶色。面板经 Portal 渲染（见 ui/popover），
 * 不会被表格外层 `overflow-hidden` 裁切。管理端各列表头共用。
 */
export function FilterMenu({
  active,
  label,
  className,
  children,
}: {
  active: boolean
  label: string
  className?: string
  children: ReactNode
}) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={`筛选${label}`}
          className={cn('rounded p-0.5 transition-colors hover:text-ink', active ? 'text-accent' : 'text-quiet')}
        >
          <ListFilter className="size-3.5" />
        </button>
      </PopoverTrigger>
      <PopoverContent className={className}>{children}</PopoverContent>
    </Popover>
  )
}

/** 单选选项列表（状态 / 角色 / 积分包等）：点选即回填并关闭面板。 */
export function OptionList({
  value,
  options,
  onPick,
}: {
  value: string
  options: readonly { value: string; label: string }[]
  onPick: (v: string) => void
}) {
  return (
    <div className="flex flex-col">
      {options.map((o) => (
        <PopoverClose asChild key={o.value}>
          <button
            type="button"
            onClick={() => onPick(o.value)}
            className={cn(
              'rounded px-2 py-1.5 text-left hover:bg-tint/40',
              value === o.value ? 'text-accent' : 'text-ink',
            )}
          >
            {o.label}
          </button>
        </PopoverClose>
      ))}
    </div>
  )
}

/** 文本搜索面板（用户名 / 订单号等）：输入即回填，不自动关闭。 */
export function SearchFilter({
  value,
  placeholder,
  onChange,
}: {
  value: string
  placeholder: string
  onChange: (v: string) => void
}) {
  return (
    <>
      <Input
        autoFocus
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-8"
      />
      {value && (
        <button
          type="button"
          className="mt-2 text-[12px] text-quiet hover:text-ink"
          onClick={() => onChange('')}
        >
          清除
        </button>
      )}
    </>
  )
}

/** 日期区间面板（原生日历，从 / 到 均可选）。空串表示不限。 */
export function DateRangeFilter({
  from,
  to,
  onChange,
}: {
  from: string
  to: string
  onChange: (from: string, to: string) => void
}) {
  return (
    <div className="flex flex-col gap-2">
      <label className="text-[12px] text-quiet">
        从
        <input
          type="date"
          value={from}
          max={to || undefined}
          onChange={(e) => onChange(e.target.value, to)}
          className={dateInputClass}
        />
      </label>
      <label className="text-[12px] text-quiet">
        到
        <input
          type="date"
          value={to}
          min={from || undefined}
          onChange={(e) => onChange(from, e.target.value)}
          className={dateInputClass}
        />
      </label>
      {(from || to) && (
        <button
          type="button"
          className="self-start text-[12px] text-quiet hover:text-ink"
          onClick={() => onChange('', '')}
        >
          清除
        </button>
      )}
    </div>
  )
}
