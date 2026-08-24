import { useState, useSyncExternalStore } from 'react'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import type { GradeResultItem, RevisedQuestion } from '@/types/api'
import { cn } from '@/lib/utils'
import { speakStem, subscribePlayingState, isGloballyPlaying } from '@/lib/tts'

interface ListeningSingleChoiceFieldProps {
  question: RevisedQuestion
  mode: 'answering' | 'review'
  value?: string
  onChange?: (v: string) => void
  result?: GradeResultItem
}

/**
 * 听力选择题（handoff 第 5 屏）：播放控件 + 男女声标注的听力原文 +
 * 纵向选项列表（与 SingleChoiceField 一致）。
 *
 * 橙红是唯一品牌色，M/W 仅用文字标签区分，
 * 不使用 blue/pink（违反 one chroma rule）。
 */
export function ListeningSingleChoiceField({
  question,
  mode,
  value,
  onChange,
  result,
}: ListeningSingleChoiceFieldProps) {
  const [isPlaying, setIsPlaying] = useState(false)
  const globallyPlaying = useSyncExternalStore(subscribePlayingState, isGloballyPlaying)
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
    <div className="flex flex-col gap-3.5">
      {/* 播放控件 */}
      <button
        onClick={handlePlay}
        disabled={isPlaying || globallyPlaying}
        className={cn(
          'flex w-fit items-center gap-2 rounded-sm border px-4 py-2 font-ui text-[14px] transition-colors',
          isPlaying || globallyPlaying
            ? 'cursor-not-allowed border-ink-15 text-quiet'
            : 'border-ink-20 text-ink hover:border-ink hover:bg-tint',
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

      {/* 听力原文：做题态隐藏（仅靠听），交卷后 review 态才呈现 */}
      {mode === 'review' && question.stem && (
        <div className="flex flex-col gap-1 text-[15px] leading-[1.9]">
          {question.stem.split('\n').map((line, index) => {
            const speakerMatch = line.match(/^(M|W):\s*(.*)$/)
            if (speakerMatch) {
              const [, speaker, text] = speakerMatch
              return (
                <p key={index} className="text-muted-ink">
                  <span className="mr-2 font-mono text-[13px] text-quiet">
                    {speaker === 'M' ? '♂ M' : '♀ W'}
                  </span>
                  <span>{text}</span>
                </p>
              )
            }
            return (
              <p key={index} className="font-bold text-ink">
                {line}
              </p>
            )
          })}
        </div>
      )}

      {/* 选项（与 SingleChoiceField 一致的纵向布局） */}
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
                    ? 'border-ink bg-ink text-paper'
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
                    ? 'border-success bg-success-wash text-ink'
                    : isUser
                      ? 'border-accent bg-wash text-muted-ink'
                      : 'border-ink-15 text-quiet',
                )}
              >
                <span className="mr-4 shrink-0 font-mono text-[13px] opacity-70">{opt.label}</span>
                <span>{opt.text}</span>
                {isCorrect && <span className="ml-auto pl-3 font-bold text-success">✓</span>}
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
