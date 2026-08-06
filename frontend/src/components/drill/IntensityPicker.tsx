import { cn } from '@/lib/utils'
import { MemberPill } from '@/components/UpgradeDialog'
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
  /** 非会员（useMembership().locked）：真题原样档点击不选中，改走 onLockedIntensity */
  memberLocked: boolean
  onLockedIntensity: () => void
}

/**
 * 出题方式三档分段按钮。锁定档（阅读首字母固定 original）不渲染控件，
 * 只给一行说明；「真题原样」对非会员挂 MemberPill 并拦去升级弹窗。
 */
export function IntensityPicker({
  config,
  value,
  onChange,
  memberLocked,
  onLockedIntensity,
}: IntensityPickerProps) {
  return (
    <div className="flex flex-col gap-3">
      <span className="font-ui text-[11px] font-bold tracking-[0.14em] text-quiet">出题方式</span>
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
                  className={cn(
                    'inline-flex items-center gap-1.5 rounded-sm border px-3 py-1.5 font-ui text-[13px] transition-colors',
                    selected
                      ? 'border-accent bg-wash text-accent'
                      : 'border-hairline text-muted-ink hover:border-accent hover:text-accent',
                  )}
                  onClick={() => {
                    if (tier.value === 'original' && memberLocked) {
                      onLockedIntensity()
                      return
                    }
                    onChange(tier.value)
                  }}
                >
                  {tier.label}
                  {tier.value === 'original' && memberLocked && <MemberPill />}
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
