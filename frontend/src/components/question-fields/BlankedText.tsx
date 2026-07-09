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

/** 填空线输入框（Spec F § 4.4）：只有底边线的内联输入。 */
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
      className="mx-1 inline-block min-w-[150px] border-0 border-b-[1.5px] border-ink bg-transparent px-2 text-center font-semibold text-ink outline-none focus:border-b-2"
    />
  )
}

/** review 态的已填答案展示：填空线上的静态文字。 */
function BlankValue({ text }: { text: string }) {
  return (
    <span className="mx-1 inline-block min-w-[100px] border-b-[1.5px] border-ink px-2 text-center font-semibold text-ink">
      {text.trim() === '' ? ' ' : text}
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
      <p className="font-question text-[15px] leading-[1.9] text-foreground">
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
      <p className="font-question text-[15px] leading-[1.7] text-foreground">{text}</p>
      <div className="flex flex-wrap gap-x-6 gap-y-2">
        {blankKeys.map((key) => (
          <span key={key} className="flex items-baseline gap-1.5 text-[13px] text-text-mid">
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

