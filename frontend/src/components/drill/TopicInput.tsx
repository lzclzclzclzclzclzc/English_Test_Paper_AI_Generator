import { cn } from '@/lib/utils'

/** 场景 chips：点击填入输入框（仍可自由改写） */
const SCENES = ['校园生活', '环保', '科技', '运动', '节日', '旅行'] as const

interface TopicInputProps {
  value: string
  onChange: (topic: string) => void
  /** intensity === 'original' 时整块置灰（真题原样不吃主题词） */
  disabled: boolean
}

/**
 * 主题词输入（仅语法三类）：场景 chips 快填 + 细线 input 自由写。
 * 主题非空会让 composeQuery 自动升为全新出题（fresh），预警由 validateCompose 给出。
 */
export function TopicInput({ value, onChange, disabled }: TopicInputProps) {
  return (
    <div className={cn('flex flex-col gap-3 transition-opacity', disabled && 'opacity-50')}>
      <span className="font-ui text-[11px] font-bold tracking-[0.14em] text-quiet">
        主题（可选）
      </span>
      <div className="flex flex-wrap gap-2">
        {SCENES.map((scene) => (
          <button
            key={scene}
            type="button"
            disabled={disabled}
            className={cn(
              'rounded-sm border px-3 py-1 font-ui text-[12.5px] transition-colors disabled:pointer-events-none',
              value === scene
                ? 'border-accent bg-wash text-accent'
                : 'border-hairline text-muted-ink hover:border-accent hover:text-accent',
            )}
            onClick={() => onChange(scene)}
          >
            {scene}
          </button>
        ))}
      </div>
      <input
        type="text"
        value={value}
        disabled={disabled}
        placeholder="也可以自己写，如“太空探索”"
        className="max-w-[24rem] rounded-[3px] border border-ink-20 bg-transparent px-3 py-2 text-[14px] text-ink outline-none transition-colors placeholder:text-quiet focus:border-accent disabled:pointer-events-none"
        onChange={(e) => onChange(e.target.value)}
      />
      {disabled && <p className="text-[12px] text-quiet">真题原样模式下主题不生效</p>}
    </div>
  )
}
