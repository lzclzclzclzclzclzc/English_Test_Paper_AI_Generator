import { useState } from 'react'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import type { GradeResultItem, RevisedQuestion } from '@/types/api'
import { cn } from '@/lib/utils'
import { speakStem } from '@/lib/tts'

interface ListeningSingleChoiceFieldProps {
  question: RevisedQuestion
  mode: 'answering' | 'review'
  value?: string
  onChange?: (v: string) => void
  result?: GradeResultItem
}

/** 听力选择题：播放控件 + 男女声标注的听力原文 + 双列选项 */
export function ListeningSingleChoiceField({
  question,
  mode,
  value,
  onChange,
  result,
}: ListeningSingleChoiceFieldProps) {
  const [isPlaying, setIsPlaying] = useState(false)
  const options = question.options ?? []
  const userLabel =
    mode === 'review' && typeof result?.user_answer === 'string'
      ? result.user_answer.trim().toUpperCase()
      : undefined
  const correctLabel =
    mode === 'review' && typeof result?.correct_answer === 'string'
      ? result.correct_answer.trim().toUpperCase()
      : undefined

  const handlePlay = async () => {
    if (!question.stem) return
    setIsPlaying(true)
    try {
      await speakStem(question.stem)
    } finally {
      setIsPlaying(false)
    }
  }

  return (
    <div className="flex flex-col gap-3">
      {/* 播放控件 */}
      <button
        onClick={handlePlay}
        disabled={isPlaying}
        className={cn(
          'flex w-fit items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-all',
          isPlaying
            ? 'bg-muted text-muted-foreground cursor-not-allowed'
            : 'bg-ink text-paper hover:bg-ink/90',
        )}
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className="h-4 w-4"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          {isPlaying ? (
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          ) : (
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"
            />
          )}
        </svg>
        <span>{isPlaying ? '播放中...' : '播放听力'}</span>
      </button>

      {/* 听力原文 */}
      {question.stem && (
        <div className="space-y-1 text-sm text-text-mid">
          {question.stem.split('\n').map((line, index) => {
            const speakerMatch = line.match(/^(M|W):\s*(.*)$/)
            if (speakerMatch) {
              const [, speaker, text] = speakerMatch
              return (
                <p key={index}>
                  <span
                    className={cn(
                      'font-medium',
                      speaker === 'M' ? 'text-blue-600' : 'text-pink-600',
                    )}
                  >
                    {speaker === 'M' ? '男' : '女'}:
                  </span>
                  <span className="ml-2 font-question">{text}</span>
                </p>
              )
            }
            return (
              <p key={index} className="font-medium font-question">
                {line}
              </p>
            )
          })}
        </div>
      )}

      {/* 选项（参考单项选择题） */}
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
                {isCorrect && (
                  <span className="ml-auto font-question font-black text-correct">
                    ✓
                  </span>
                )}
                {isUser && !isCorrect && (
                  <span className="ml-auto font-question font-black text-wrong">
                    ✗
                  </span>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
