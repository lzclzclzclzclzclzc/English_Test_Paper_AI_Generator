import type { BlankMap } from '@/lib/answers'
import { blankLabel, splitTemplateByBlanks } from '@/lib/answers'

interface BlankedTextProps {
  /** 含下划线空位标记的题干/模板 */
  text: string
  /** 空位键（blank1..N，来自 getBlankKeys），顺序即输入框顺序 */
  blankKeys: string[]
  mode: 'answering' | 'review'
  value: BlankMap
  onChange?: (next: BlankMap) => void
}

/** 填空输入框（2026-08 卡片化改版）：浅底色圆角框，focus 描边转赤陶。 */
function BlankInput({
  value,
  onChange,
  ariaLabel,
}: {
  value: string
  onChange?: (v: string) => void
  ariaLabel: string
}) {
  return (
    <input
      type="text"
      aria-label={ariaLabel}
      value={value}
      onChange={(e) => onChange?.(e.target.value)}
      className="mx-1 inline-block min-w-[10rem] rounded-md border border-ink-15 bg-tint px-3 py-1 text-center text-ink outline-none transition-colors focus:border-accent focus:bg-card-surface focus:ring-2 focus:ring-accent/15"
    />
  )
}

/** review 态的已填答案展示：已填 = 深色字薄底框，未填 = 虚线框占位灰。 */
function BlankValue({ text }: { text: string }) {
  const filled = text.trim() !== ''
  if (filled) {
    return (
      <span className="mx-1 inline-block min-w-[6rem] rounded-md bg-tint px-3 py-1 text-center font-semibold text-ink">
        {text}
      </span>
    )
  }
  return (
    <span className="mx-1 inline-block min-w-[6rem] rounded-md border border-dashed border-ink-30 px-3 py-1 text-center text-[14px] text-quiet">
      未作答
    </span>
  )
}

/**
 * 把带空位的英文句子渲染为"文字 + 内联输入框"。
 * 仅当文本中下划线连串段数 === 空数时原位内联；否则整句原样展示、
 * 输入框带"空N"标签排在下方（应对真题库中 51/220 的标记不一致数据）。
 */
export function BlankedText({ text, blankKeys, mode, value, onChange }: BlankedTextProps) {
  const segments = splitTemplateByBlanks(text, blankKeys.length)

  const setBlank = (key: string, v: string) => onChange?.({ ...value, [key]: v })

  if (segments) {
    return (
      <p className="text-[17px] leading-[1.9] text-ink">
        {segments.map((seg, i) => {
          const key = blankKeys[i]
          return (
            <span key={i}>
              {seg}
              {i < blankKeys.length && key !== undefined && (
                mode === 'answering' ? (
                  <BlankInput
                    ariaLabel={blankLabel(key)}
                    value={value[key] ?? ''}
                    onChange={(v) => setBlank(key, v)}
                  />
                ) : (
                  <BlankValue text={value[key] ?? ''} />
                )
              )}
            </span>
          )
        })}
      </p>
    )
  }

  // 兜底：空位标记与空数不符 → 原文 + 标签输入框
  return (
    <div className="flex flex-col gap-2.5">
      <p className="text-[17px] leading-[1.9] text-ink">{text}</p>
      <div className="flex flex-wrap gap-x-6 gap-y-2">
        {blankKeys.map((key) => (
          <span key={key} className="flex items-baseline gap-1.5 text-[13px] text-muted-ink">
            {blankLabel(key)}：
            {mode === 'answering' ? (
              <BlankInput
                ariaLabel={blankLabel(key)}
                value={value[key] ?? ''}
                onChange={(v) => setBlank(key, v)}
              />
            ) : (
              <BlankValue text={value[key] ?? ''} />
            )}
          </span>
        ))}
      </div>
    </div>
  )
}
