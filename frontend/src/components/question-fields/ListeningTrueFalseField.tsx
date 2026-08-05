import type { GradeResultItem, RevisedQuestion } from '@/types/api'
import { cn } from '@/lib/utils'

interface ListeningTrueFalseFieldProps {
  question: RevisedQuestion
  mode: 'answering' | 'review'
  value?: string
  onChange?: (v: string) => void
  result?: GradeResultItem
}

/**
 * 听力判断题（listening_true_false）：True / False 二选一。
 *
 * passage 不在此组件渲染——由外层 PassageBlock 统一渲染一次。
 * 做题态与 review 态的样式参考 ListeningSingleChoiceField 的选项区
 * （Kissaten：terracotta 高亮正确，ink-30 标注用户错选）。
 */
export function ListeningTrueFalseField({
  question,
  mode,
  value,
  onChange,
  result,
}: ListeningTrueFalseFieldProps) {
  const choices: Array<'T' | 'F'> = ['T', 'F']
  const userLabel =
    mode === 'review' && typeof result?.user_answer === 'string'
      ? result.user_answer.trim().toUpperCase()
      : undefined
  const correctLabel =
    mode === 'review' && typeof result?.correct_answer === 'string'
      ? result.correct_answer.trim().toUpperCase()
      : undefined

  return (
    <div className="flex flex-col gap-3.5">
      {/* 判断句（stem） */}
      {question.stem && (
        <p className="text-[15px] leading-[1.8] text-ink">{question.stem}</p>
      )}

      {/* True / False 按钮 */}
      {mode === 'answering' ? (
        <div className="flex max-w-[34rem] gap-3">
          {choices.map((choice) => {
            const selected = value === choice
            return (
              <button
                key={choice}
                type="button"
                onClick={() => onChange?.(choice)}
                className={cn(
                  'flex-1 cursor-pointer rounded-sm border px-4 py-[11px] text-[15px] transition-colors',
                  selected
                    ? 'border-accent bg-wash text-ink'
                    : 'border-ink-15 text-muted-ink hover:bg-tint',
                )}
              >
                <span className="mr-3 font-mono text-[13px] opacity-70">{choice}</span>
                {choice === 'T' ? 'True' : 'False'}
              </button>
            )
          })}
        </div>
      ) : (
        <div className="flex max-w-[34rem] gap-3">
          {choices.map((choice) => {
            const isUser = userLabel === choice
            const isCorrect = correctLabel === choice
            return (
              <div
                key={choice}
                className={cn(
                  'flex-1 rounded-sm border px-4 py-[11px] text-[15px]',
                  isCorrect
                    ? 'border-accent bg-wash text-ink'
                    : isUser
                      ? 'border-ink-30 text-muted-ink'
                      : 'border-ink-15 text-quiet',
                )}
              >
                <span className="mr-3 font-mono text-[13px] opacity-70">{choice}</span>
                {choice === 'T' ? 'True' : 'False'}
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
