import { useCredits } from '@/hooks/useCredits'
import { INTENSITY_ACTION } from '@/lib/creditsActions'
import type { Intensity } from '@/lib/composeQuery'
import type { DrillConfig } from '@/lib/drillConfig'

/** 三档顺序与文案（composeQuery 的 RevisionMode 三档） */
const TIERS: ReadonlyArray<{ value: Intensity; label: string; desc: string }> = [
  { value: 'original', label: '真题原样', desc: '真题原样：一模二模真题，不做任何改动' },
  { value: 'light', label: 'AI 改编', desc: 'AI 改编：保留题目结构，换词换语境' },
  { value: 'fresh', label: '全新出题', desc: '全新出题：按所选考点从零命题' },
]

interface IntensityPickerProps {
  /** DrillConfig.intensity：三档可选或锁定单档 */
  config: DrillConfig['intensity']
  value: Intensity
  onChange: (i: Intensity) => void
}

/**
 * 出题方式三档分段按钮。锁定档（阅读首字母固定 original）不渲染控件，
 * 只给一行说明；每档旁标「每题 N 积分」，三档按 AI 介入程度递增计价。
 */
export function IntensityPicker({ config, value, onChange }: IntensityPickerProps) {
  const { priceTable } = useCredits()
  const perQuestion = (tier: Intensity): number | null =>
    priceTable?.items.find((p) => p.action === INTENSITY_ACTION[tier])?.per_unit ?? null
  return (
    <div className="flex flex-col gap-3">
      <span className="kicker">出题方式</span>
      {'locked' in config ? (
        <p className="text-[12.5px] text-quiet">此题型固定使用真题原文，不做改写</p>
      ) : (
        <>
          <div className="flex flex-wrap gap-2">
            {TIERS.map((tier) => {
              const selected = value === tier.value
              return (
                <button
                  key={tier.value}
                  type="button"
                  aria-pressed={selected}
                  className="seg gap-1.5"
                  onClick={() => onChange(tier.value)}
                >
                  {tier.label}
                  {perQuestion(tier.value) !== null && (
                    <span className={`font-ui text-[11px] tabular-nums ${selected ? 'opacity-70' : 'text-quiet'}`}>
                      {perQuestion(tier.value)} 积分/题
                    </span>
                  )}
                </button>
              )
            })}
          </div>
          <p className="text-[12px] text-quiet">
            {TIERS.find((t) => t.value === value)?.desc}
          </p>
        </>
      )}
    </div>
  )
}
