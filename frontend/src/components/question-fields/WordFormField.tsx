import type { GradeResultItem, RevisedQuestion } from '@/types/api'
import type { BlankMap } from '@/lib/answers'
import { getBlankKeys, toBlankMap } from '@/lib/answers'
import { BlankedText } from '@/components/question-fields/BlankedText'

interface WordFormFieldProps {
  question: RevisedQuestion
  mode: 'answering' | 'review'
  value?: BlankMap
  onChange?: (v: BlankMap) => void
  result?: GradeResultItem
}

/** 词形转换：题干内联填空线 + 提示词。 */
export function WordFormField({ question, mode, value, onChange, result }: WordFormFieldProps) {
  const blankKeys = getBlankKeys(question.answer)
  const displayValue =
    mode === 'review' ? toBlankMap(blankKeys, result?.user_answer) : (value ?? {})

  const stem = question.stem ?? ''
  const showHint = question.hint && !stem.includes(question.hint)

  return (
    <div className="flex flex-col gap-1.5">
      <BlankedText
        text={stem}
        blankKeys={blankKeys}
        mode={mode}
        value={displayValue}
        onChange={onChange}
      />
      {showHint && (
        <p className="text-[13px] text-muted-ink">（用 {question.hint} 的适当形式填空）</p>
      )}
    </div>
  )
}
