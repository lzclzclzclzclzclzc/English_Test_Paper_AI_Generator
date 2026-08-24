import type { GradeResultItem, RevisedQuestion } from '@/types/api'
import type { BlankMap } from '@/lib/answers'
import { getBlankKeys, toBlankMap } from '@/lib/answers'
import { BlankedText } from '@/components/question-fields/BlankedText'

interface SentenceRewritingFieldProps {
  question: RevisedQuestion
  mode: 'answering' | 'review'
  value?: BlankMap
  onChange?: (v: BlankMap) => void
  result?: GradeResultItem
}

/** 句子改写：原句 + 中文指令 + 带空模板（空数由 answer 键数决定，见 lib/answers）。 */
export function SentenceRewritingField({
  question,
  mode,
  value,
  onChange,
  result,
}: SentenceRewritingFieldProps) {
  const blankKeys = getBlankKeys(question.answer)
  const displayValue =
    mode === 'review' ? toBlankMap(blankKeys, result?.user_answer) : (value ?? {})

  return (
    <div className="flex flex-col gap-2">
      {question.original_sentence && (
        <p className="text-[17px] leading-[1.9] text-ink">
          {question.original_sentence}
        </p>
      )}
      {question.instruction && (
        <span className="chip self-start border-accent/30 bg-wash px-2.5 py-1 text-[13px] leading-normal text-accent">
          {question.instruction}
        </span>
      )}
      <BlankedText
        text={question.template}
        blankKeys={blankKeys}
        mode={mode}
        value={displayValue}
        onChange={onChange}
      />
    </div>
  )
}
