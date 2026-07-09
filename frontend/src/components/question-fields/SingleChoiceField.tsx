import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import type { GradeResultItem, RevisedQuestion } from '@/types/api'
import { cn } from '@/lib/utils'

interface SingleChoiceFieldProps {
  question: RevisedQuestion
  mode: 'answering' | 'review'
  value?: string
  onChange?: (v: string) => void
  result?: GradeResultItem
}

/** 单选题（Spec F § 5 选择题选项）：双列选项 grid，字母圆圈 + 选中实心。 */
export function SingleChoiceField({
  question,
  mode,
  value,
  onChange,
  result,
}: SingleChoiceFieldProps) {
  const options = question.options ?? []
  const userLabel = mode === 'review' && typeof result?.user_answer === 'string'
    ? result.user_answer.trim().toUpperCase()
    : undefined
  const correctLabel =
    mode === 'review' && typeof result?.correct_answer === 'string'
      ? result.correct_answer.trim().toUpperCase()
      : undefined

  return (
    <div className="flex flex-col gap-3">
      {question.stem && (
        <p className="font-question text-[15px] leading-[1.7] text-foreground">
          {question.stem}
        </p>
      )}

      {mode === 'answering' ? (
        <RadioGroup
          value={value ?? ''}
          onValueChange={(v) => onChange?.(v)}
          className="grid grid-cols-2 gap-2 max-sm:grid-cols-1"
        >
          {options.map((opt) => {
            const selected = value === opt.label
            return (
              <label
                key={opt.label}
                className={cn(
                  'flex cursor-pointer items-center gap-2.5 rounded-md px-3.5 py-2 text-sm transition-colors',
                  selected
                    ? 'border-[1.5px] border-ink bg-ink-wash font-medium'
                    : 'border border-line-strong bg-sheet hover:border-muted-foreground',
                )}
              >
                <RadioGroupItem value={opt.label} className="sr-only" />
                <span
                  className={cn(
                    'flex size-5 shrink-0 items-center justify-center rounded-full text-xs',
                    selected
                      ? 'bg-ink font-bold text-paper'
                      : 'border-[1.5px] border-line-strong text-text-mid',
                  )}
                >
                  {opt.label}
                </span>
                <span className="font-question">{opt.text}</span>
              </label>
            )
          })}
        </RadioGroup>
      ) : (
        <div className="grid grid-cols-2 gap-2 max-sm:grid-cols-1">
          {options.map((opt) => {
            const isUser = userLabel === opt.label
            const isCorrect = correctLabel === opt.label
            return (
              <div
                key={opt.label}
                className={cn(
                  'flex items-center gap-2.5 rounded-md px-3.5 py-2 text-sm',
                  isCorrect
                    ? 'border-[1.5px] border-correct'
                    : isUser
                      ? 'border-[1.5px] border-wrong'
                      : 'border border-line-strong bg-sheet opacity-70',
                )}
              >
                <span
                  className={cn(
                    'flex size-5 shrink-0 items-center justify-center rounded-full text-xs',
                    isCorrect
                      ? 'bg-correct font-bold text-paper'
                      : isUser
                        ? 'bg-wrong font-bold text-paper'
                        : 'border-[1.5px] border-line-strong text-text-mid',
                  )}
                >
                  {opt.label}
                </span>
                <span className="font-question">{opt.text}</span>
                {isCorrect && <span className="ml-auto font-question font-black text-correct">✓</span>}
                {isUser && !isCorrect && (
                  <span className="ml-auto font-question font-black text-wrong">✗</span>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
