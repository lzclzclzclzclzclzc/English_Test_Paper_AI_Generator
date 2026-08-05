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

/**
 * 单选题（handoff 第 5 屏）：34rem 宽纵向选项列表，选项字母等宽 13px，
 * 选中 = 赤陶边 + accent-wash 底。review 态：正确项赤陶实边 + ✓，
 * 错选项 ✕ 赤陶字。
 */
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
    <div className="flex flex-col gap-3.5">
      {question.stem && (
        <p className="text-[17px] leading-[1.9] text-ink">{question.stem}</p>
      )}

      {mode === 'answering' ? (
        <RadioGroup
          value={value ?? ''}
          onValueChange={(v) => onChange?.(v)}
          className="flex max-w-[34rem] flex-col gap-2"
        >
          {options.map((opt) => {
            const selected = value === opt.label
            return (
              <label
                key={opt.label}
                className={cn(
                  'flex cursor-pointer items-baseline rounded-sm border px-4 py-2.5 text-[15px] transition-colors',
                  selected
                    ? 'border-accent bg-wash text-ink'
                    : 'border-ink-15 text-muted-ink hover:bg-tint',
                )}
              >
                <RadioGroupItem value={opt.label} className="sr-only" />
                <span className="mr-4 shrink-0 font-mono text-[13px] opacity-70">{opt.label}</span>
                <span>{opt.text}</span>
              </label>
            )
          })}
        </RadioGroup>
      ) : (
        <div className="flex max-w-[34rem] flex-col gap-2">
          {options.map((opt) => {
            const isUser = userLabel === opt.label
            const isCorrect = correctLabel === opt.label
            return (
              <div
                key={opt.label}
                className={cn(
                  'flex items-baseline rounded-sm border px-4 py-2.5 text-[15px]',
                  isCorrect
                    ? 'border-accent bg-wash text-ink'
                    : isUser
                      ? 'border-ink-30 text-muted-ink'
                      : 'border-ink-15 text-quiet',
                )}
              >
                <span className="mr-4 shrink-0 font-mono text-[13px] opacity-70">{opt.label}</span>
                <span>{opt.text}</span>
                {isCorrect && <span className="ml-auto pl-3 font-bold text-accent">✓</span>}
                {isUser && !isCorrect && (
                  <span className="ml-auto pl-3 font-bold text-accent">✕</span>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
