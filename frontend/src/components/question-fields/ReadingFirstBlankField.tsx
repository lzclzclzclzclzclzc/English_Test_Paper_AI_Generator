import type { ReactNode } from 'react'
import type { GradeResultItem, RevisedQuestion } from '@/types/api'
import type { BlankMap } from '@/lib/answers'
import { getBlankKeys, toBlankMap } from '@/lib/answers'
import { cn } from '@/lib/utils'

interface ReadingFirstBlankFieldProps {
  question: RevisedQuestion
  mode: 'answering' | 'review'
  value?: BlankMap
  onChange?: (v: BlankMap) => void
  result?: GradeResultItem
}

/** 空位标记：{首字母}{至少 2 下划线}({题号}){至少 2 下划线}，如 a______(1)____ */
const MARKER_RE = /([A-Za-z])_{2,}\((\d+)\)_{2,}/g

interface BlankMarker {
  letter: string
  number: number
  blankKey: string
  start: number
  end: number
}

/** 解析 passage_json.content 中的空位标记，按出现顺序返回。 */
function parseMarkers(content: string): BlankMarker[] {
  const markers: BlankMarker[] = []
  let m: RegExpExecArray | null
  MARKER_RE.lastIndex = 0
  while ((m = MARKER_RE.exec(content)) !== null) {
    markers.push({
      letter: m[1] ?? '',
      number: Number(m[2] ?? '0'),
      blankKey: `blank${m[2] ?? '0'}`,
      start: m.index,
      end: m.index + m[0].length,
    })
  }
  return markers
}

/** 答题态：首字母 + 浅底输入框（输入空位剩余部分），focus 描边转橙红。 */
function BlankInput({
  letter,
  value,
  onChange,
  ariaLabel,
}: {
  letter: string
  value: string
  onChange?: (v: string) => void
  ariaLabel: string
}) {
  return (
    <span className="whitespace-nowrap">
      <span className="font-bold text-accent">{letter}</span>
      <input
        type="text"
        aria-label={ariaLabel}
        value={value}
        onChange={(e) => onChange?.(e.target.value)}
        className="mx-0.5 inline-block min-w-[6rem] rounded-md border border-ink-15 bg-tint px-2 py-0.5 text-center text-ink outline-none transition-colors focus:border-accent focus:bg-card-surface focus:ring-2 focus:ring-accent/15"
      />
    </span>
  )
}

/** 复盘态：首字母 + 剩余部分。已填 = 深色字薄底框，未填 = 虚线框占位灰。 */
function BlankValue({ letter, value }: { letter: string; value: string }) {
  const filled = value.trim() !== ''
  return (
    <span className="whitespace-nowrap">
      <span className="font-bold text-accent">{letter}</span>
      <span
        className={cn(
          'mx-0.5 inline-block min-w-[4rem] rounded-md px-2 py-0.5 text-center',
          filled
            ? 'bg-tint font-bold text-ink'
            : 'border border-dashed border-ink-30 text-[13px] text-quiet',
        )}
      >
        {filled ? value : '未填'}
      </span>
    </span>
  )
}

/**
 * 阅读首字母填空：整篇文章单栏渲染，空位内联（首字母 + 输入框）。
 * 提交/复盘值均为「首字母 + 用户输入」拼成的完整单词，后端按完整单词判空。
 */
export function ReadingFirstBlankField({
  question,
  mode,
  value,
  onChange,
  result,
}: ReadingFirstBlankFieldProps) {
  const blankKeys = getBlankKeys(question.answer)
  const content = question.passage_json?.content ?? ''
  const markers = parseMarkers(content)

  const displayValue =
    mode === 'review' ? toBlankMap(blankKeys, result?.user_answer) : (value ?? {})

  const setBlank = (key: string, letter: string, v: string) =>
    onChange?.({ ...displayValue, [key]: letter + v })

  // 无空位标记（或标记与答案键数不符）→ 兜底：原文 + 单词级标签输入框
  if (markers.length === 0 || markers.length !== blankKeys.length) {
    return (
      <div className="flex w-full flex-col gap-2.5">
        <p className="whitespace-pre-wrap text-[15px] leading-[1.8] text-ink">{content}</p>
        <div className="flex flex-wrap gap-x-6 gap-y-2">
          {blankKeys.map((key) => {
            const full = displayValue[key] ?? ''
            const letter = full.trim() === '' ? '' : full[0] ?? ''
            const rest = full.trim() === '' ? '' : full.slice(1)
            return (
              <span
                key={key}
                className="flex items-baseline gap-1.5 text-[13px] text-muted-ink"
              >
                {key.replace('blank', '空')}：
                {mode === 'answering' ? (
                  <BlankInput
                    letter={letter}
                    ariaLabel={key.replace('blank', '空')}
                    value={rest}
                    onChange={(v) => setBlank(key, letter, v)}
                  />
                ) : (
                  <BlankValue letter={letter} value={rest} />
                )}
              </span>
            )
          })}
        </div>
      </div>
    )
  }

  // 常规：原位内联渲染
  const parts: ReactNode[] = []
  let cursor = 0
  for (const mk of markers) {
    parts.push(content.slice(cursor, mk.start))
    const full = displayValue[mk.blankKey] ?? ''
    const rest = full.trim() === '' ? '' : full.startsWith(mk.letter) ? full.slice(mk.letter.length) : full
    parts.push(
      mode === 'answering' ? (
        <BlankInput
          key={mk.blankKey}
          letter={mk.letter}
          ariaLabel={`空${mk.number}`}
          value={rest}
          onChange={(v) => setBlank(mk.blankKey, mk.letter, v)}
        />
      ) : (
        <BlankValue key={mk.blankKey} letter={mk.letter} value={rest} />
      ),
    )
    cursor = mk.end
  }
  parts.push(content.slice(cursor))

  return (
    <div className="w-full whitespace-pre-wrap text-[15px] leading-[1.8] text-ink">
      {parts}
    </div>
  )
}