import { cn } from '@/lib/utils'

interface CountSelectorProps {
  /** 档位数字（来自 DrillConfig.countPresets） */
  presets: readonly number[]
  /** 步进上限（单题型上限，全局 30 题由 validateCompose 再兜底） */
  max: number
  unit: '道' | '篇'
  /** 「每篇固定 6 题」等换算说明，quiet 小字 */
  unitHint?: string
  value: number
  onChange: (n: number) => void
}

/**
 * 题量选择：档位分段按钮 + 小步进（− / 数字 / +）。
 * 档位选中 = 赤陶边 + wash 底；步进到非档位值时无档位选中。
 */
export function CountSelector({ presets, max, unit, unitHint, value, onChange }: CountSelectorProps) {
  const clamp = (n: number) => Math.min(max, Math.max(1, n))

  return (
    <div className="flex flex-col gap-3">
      <span className="font-ui text-[11px] font-bold tracking-[0.14em] text-quiet">题量</span>
      <div className="flex flex-wrap items-center gap-x-5 gap-y-3">
        <div className="flex items-center gap-2">
          {presets.map((n) => (
            <button
              key={n}
              type="button"
              className={cn(
                'min-w-11 rounded-sm border px-3 py-1.5 font-ui text-[13.5px] font-[550] tabular-nums transition-colors',
                value === n
                  ? 'border-accent bg-wash text-ink'
                  : 'border-hairline text-muted-ink hover:border-accent hover:text-accent',
              )}
              onClick={() => onChange(n)}
            >
              {n}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            aria-label="减少题量"
            disabled={value <= 1}
            className="flex size-7 items-center justify-center rounded-sm border border-hairline font-ui text-[15px] leading-none text-muted-ink transition-colors hover:border-accent hover:text-accent disabled:pointer-events-none disabled:opacity-40"
            onClick={() => onChange(clamp(value - 1))}
          >
            −
          </button>
          <span className="min-w-12 text-center font-ui text-[15px] font-[650] tabular-nums text-ink">
            {value} <span className="text-[13px] font-normal text-muted-ink">{unit}</span>
          </span>
          <button
            type="button"
            aria-label="增加题量"
            disabled={value >= max}
            className="flex size-7 items-center justify-center rounded-sm border border-hairline font-ui text-[15px] leading-none text-muted-ink transition-colors hover:border-accent hover:text-accent disabled:pointer-events-none disabled:opacity-40"
            onClick={() => onChange(clamp(value + 1))}
          >
            +
          </button>
        </div>
        {unitHint && <span className="text-[12px] text-quiet">{unitHint}</span>}
      </div>
    </div>
  )
}
