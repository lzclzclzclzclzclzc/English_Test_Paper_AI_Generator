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
        <p className="font-question text-[15px] leading-[1.7] text-foreground">
          {question.original_sentence}
        </p>
      )}
      {question.instruction && (
        <p className="text-[13px] text-muted-foreground">（{question.instruction}）</p>
      )}
      {question.template && (
        <BlankedText
          text={question.template}
          blankKeys={blankKeys}
          mode={mode}
          value={displayValue}
          onChange={onChange}
        />
      )}
    </div>
  )
}
