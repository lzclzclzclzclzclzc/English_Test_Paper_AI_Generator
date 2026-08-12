import { cn } from '@/lib/utils'
import { useKnowledgePoints } from '@/hooks/useKnowledgePoints'
import { HIDDEN_KP_IDS, THIN_KP_IDS } from '@/lib/drillConfig'
import type { QuestionType } from '@/types/api'

interface KpPickerProps {
  /** 只展示 level1 === type 的知识点（仅语法三类有细分） */
  type: QuestionType
  value: string[]
  onChange: (ids: string[]) => void
}

/**
 * 考点多选 chips：不选 = 不限。零题量考点（HIDDEN_KP_IDS）直接不进列表；
 * 薄尾考点（THIN_KP_IDS）加「题量少」角注，选中时再给一行事前预警。
 */
export function KpPicker({ type, value, onChange }: KpPickerProps) {
  const { data, isLoading } = useKnowledgePoints()
  const kps = data?.filter((kp) => kp.level1 === type && !HIDDEN_KP_IDS.has(kp.id)) ?? []
  const thinSelected = value.some((id) => THIN_KP_IDS.has(id))

  const toggle = (id: string) =>
    onChange(value.includes(id) ? value.filter((v) => v !== id) : [...value, id])

  return (
    <div className="flex flex-col gap-3">
      <span className="font-ui text-[11px] font-bold tracking-[0.14em] text-quiet">
        考点（可多选，不选 = 不限）
      </span>
      {isLoading ? (
        <span className="text-[12.5px] text-quiet">考点目录加载中…</span>
      ) : kps.length === 0 ? (
        <span className="text-[12.5px] text-quiet">考点目录暂不可用，可直接不限考点出题</span>
      ) : (
        <div className="flex flex-wrap gap-2">
          {kps.map((kp) => {
            const selected = value.includes(kp.id)
            return (
              <button
                key={kp.id}
                type="button"
                className={cn(
                  'rounded-sm border px-3 py-1 font-ui text-[12.5px] transition-colors',
                  selected
                    ? 'border-accent bg-wash text-accent'
                    : 'border-hairline text-muted-ink hover:border-accent hover:text-accent',
                )}
                onClick={() => toggle(kp.id)}
              >
                {kp.level2}
                {THIN_KP_IDS.has(kp.id) && (
                  <sup className="ml-0.5 text-[10.5px] font-normal text-quiet">题量少</sup>
                )}
              </button>
            )
          })}
        </div>
      )}
      {thinSelected && (
        <p className="text-[12px] text-quiet">
          所选考点真题较少，可能凑不满题量；想要足量可改用“全新出题”档
        </p>
      )}
    </div>
  )
}
