import type { GradeResultItem, RevisedQuestion } from '@/types/api'
import type { BlankMap } from '@/lib/answers'
import { getBlankKeys, toBlankMap } from '@/lib/answers'
import { BlankedText } from '@/components/question-fields/BlankedText'

interface ListeningFillBlankFieldProps {
  question: RevisedQuestion
  mode: 'answering' | 'review'
  value?: BlankMap
  onChange?: (v: BlankMap) => void
  result?: GradeResultItem
}

/**
 * 听力填词：带空句（stem）用填空线输入框渲染，空数由 answer 键数决定。
 * 听力材料（passage）不在此渲染——由 PaperPage 按 passage_id 分组统一渲染一次。
 */
export function ListeningFillBlankField({
  question,
  mode,
  value,
  onChange,
  result,
}: ListeningFillBlankFieldProps) {
  const blankKeys = getBlankKeys(question.answer)
  const displayValue =
    mode === 'review' ? toBlankMap(blankKeys, result?.user_answer) : (value ?? {})

  return (
    <div className="flex flex-col gap-2">
      {question.stem && (
        <BlankedText
          text={question.stem}
          blankKeys={blankKeys}
          mode={mode}
          value={displayValue}
          onChange={onChange}
        />
      )}
    </div>
  )
}