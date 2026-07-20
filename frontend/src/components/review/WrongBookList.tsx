import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronDown } from 'lucide-react'
import type { GradeResultItem, PaperItem } from '@/types/api'
import type { WrongBookEntry } from '@/lib/wrongBook'
import { TYPE_LABELS } from '@/lib/kp'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { QuestionCard } from '@/components/QuestionCard'
import { SolutionBlock } from '@/components/SolutionBlock'

interface WrongBookListProps {
  entries: WrongBookEntry[]
  selected: Set<string>
  onToggle: (sourceQuestionId: string) => void
  onToggleAll: () => void
  onRemove: (sourceQuestionId: string) => void
  /** 解析配额用（与试卷页共享每日次数） */
  locked: boolean
  userId: string
}

/** 错题本：交卷时自动收集的错题（仅本设备），可勾选、展开复看、请求解析、移出。 */
export function WrongBookList({
  entries,
  selected,
  onToggle,
  onToggleAll,
  onRemove,
  locked,
  userId,
}: WrongBookListProps) {
  if (entries.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 rounded-md border border-dashed border-line-strong px-6 py-20 text-center">
        <p className="font-serif text-lg font-bold text-foreground">错题本还是空的</p>
        <p className="text-[13.5px] text-text-mid">
          交卷后答错的题会自动收进来，随时回来复练
        </p>
        <Button asChild className="mt-3 px-6">
          <Link to="/">去出一份卷</Link>
        </Button>
      </div>
    )
  }

  const allSelected = entries.every((e) => selected.has(e.sourceQuestionId))

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div className="flex items-baseline gap-3">
          <h2 className="font-serif text-[15px] font-bold text-foreground">
            错题本 <span className="font-sans text-[13px] font-normal">（{entries.length} 题）</span>
          </h2>
          <span className="text-xs text-muted-foreground">仅保存在本设备，重做答对会自动移出</span>
        </div>
        <label className="flex cursor-pointer items-center gap-1.5 text-[13px] text-text-mid">
          <input
            type="checkbox"
            className="size-3.5 accent-ink"
            checked={allSelected}
            onChange={onToggleAll}
          />
          全选
        </label>
      </div>

      <ul className="divide-y divide-line-soft rounded-md border border-line bg-sheet">
        {entries.map((entry, i) => (
          <WrongBookRow
            key={`${entry.sourceQuestionId}-${entry.gradedAt}`}
            entry={entry}
            ordinal={i + 1}
            checked={selected.has(entry.sourceQuestionId)}
            onToggle={() => onToggle(entry.sourceQuestionId)}
            onRemove={() => onRemove(entry.sourceQuestionId)}
            locked={locked}
            userId={userId}
          />
        ))}
      </ul>
    </div>
  )
}

function WrongBookRow({
  entry,
  ordinal,
  checked,
  onToggle,
  onRemove,
  locked,
  userId,
}: {
  entry: WrongBookEntry
  ordinal: number
  checked: boolean
  onToggle: () => void
  onRemove: () => void
  locked: boolean
  userId: string
}) {
  const [expanded, setExpanded] = useState(false)
  const { question } = entry
  const preview = question.stem ?? question.original_sentence ?? '（无题干）'
  const gradedAt = new Date(entry.gradedAt).toLocaleString('zh-CN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  })

  // 复用 QuestionCard review 态：把错题本条目还原成 PaperItem + 判分结果
  const item: PaperItem = {
    index: ordinal,
    question,
    score: entry.score,
    source_question_id: entry.sourceQuestionId,
    revision_mode: entry.revisionMode,
    revision_notes: null,
  }
  const result: GradeResultItem = {
    index: ordinal,
    user_answer: entry.userAnswer,
    correct_answer: question.answer,
    is_correct: false,
  }

  return (
    <li className="px-4 py-3">
      <div className="flex items-center gap-3">
        <input
          type="checkbox"
          className="size-3.5 shrink-0 accent-ink"
          checked={checked}
          onChange={onToggle}
          aria-label={`选中第 ${ordinal} 条错题`}
        />
        <button
          type="button"
          className="flex min-w-0 flex-1 items-center gap-2.5 text-left"
          onClick={() => setExpanded((v) => !v)}
        >
          <span className="shrink-0 rounded-full border border-line-strong px-2 py-0.5 text-xs text-text-mid">
            {TYPE_LABELS[question.question_type] ?? question.question_type}
          </span>
          <span className="min-w-0 flex-1 truncate font-question text-[14px] text-foreground">
            {preview}
          </span>
          {entry.timesWrong > 1 && (
            <span className="shrink-0 rounded-full bg-[#f6e8e4] px-2 py-0.5 text-xs font-medium text-wrong">
              错过 {entry.timesWrong} 次
            </span>
          )}
          <ChevronDown
            className={cn(
              'size-4 shrink-0 text-muted-foreground transition-transform',
              expanded && 'rotate-180',
            )}
          />
        </button>
        <button
          type="button"
          className="shrink-0 text-xs text-muted-foreground hover:text-foreground"
          onClick={onRemove}
        >
          移出
        </button>
      </div>

      <p className="mt-1 pl-[26px] text-[12.5px] text-text-mid">
        来自{' '}
        <Link to={`/papers/${entry.paperId}`} className="underline-offset-2 hover:underline">
          〈{entry.paperTitle}〉
        </Link>{' '}
        · {gradedAt}
      </p>

      {expanded && (
        <div className="mt-1 border-t border-dashed border-line pl-[26px]">
          <QuestionCard
            item={item}
            mode="review"
            result={result}
            solutionSlot={
              <SolutionBlock
                question={question}
                sourceQuestionId={entry.sourceQuestionId}
                revisionMode={entry.revisionMode}
                cacheKey={['solution', 'wrongbook', entry.sourceQuestionId, entry.gradedAt]}
                locked={locked}
                userId={userId}
              />
            }
          />
        </div>
      )}
    </li>
  )
}
