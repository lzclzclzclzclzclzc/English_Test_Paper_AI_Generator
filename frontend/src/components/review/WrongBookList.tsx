import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronDown } from 'lucide-react'
import type { GradeResultItem, PaperItem } from '@/types/api'
import type { WrongBookEntry } from '@/lib/wrongBook'
import { TYPE_LABELS } from '@/lib/kp'
import { PATHS } from '@/lib/paths'
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

/** 勾选方块（handoff 第 9 屏）：选中 = 赤陶边 + wash 底 + ✓。 */
function CheckSquare({
  checked,
  onChange,
  label,
}: {
  checked: boolean
  onChange: () => void
  label: string
}) {
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={checked}
      aria-label={label}
      onClick={onChange}
      className={cn(
        'flex size-[18px] shrink-0 items-center justify-center rounded-sm border text-[11px] leading-none transition-colors',
        checked ? 'border-accent bg-wash text-accent' : 'border-ink-20 text-transparent hover:border-ink-30',
      )}
    >
      ✓
    </button>
  )
}

/** 错题本（handoff 第 9 屏）：行式列表，交卷时自动收集（仅本设备），可勾选、展开复看、请求解析、移出。 */
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
      <div className="flex flex-col items-start gap-2 border-t border-hairline pt-8">
        <p className="text-[17px] text-ink">错题本还是空的</p>
        <p className="text-[13.5px] text-muted-ink">
          交卷后答错的题会自动收进来，随时回来复练
        </p>
        <Button asChild className="mt-3">
          <Link to={PATHS.dashboard}>去出一份卷</Link>
        </Button>
      </div>
    )
  }

  const allSelected = entries.every((e) => selected.has(e.sourceQuestionId))

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div className="flex items-baseline gap-3">
          <h2 className="text-[17px] text-ink">
            错题本 <span className="text-[13px] text-quiet">（{entries.length} 题）</span>
          </h2>
          <span className="text-[12px] text-quiet">仅保存在本设备，重做答对会自动移出</span>
        </div>
        <label className="flex cursor-pointer items-center gap-2 text-[13px] text-muted-ink">
          <CheckSquare checked={allSelected} onChange={onToggleAll} label="全选" />
          全选
        </label>
      </div>

      <ul className="border-t border-hairline">
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
    source_question_id: entry.sourceQuestionId,
    revision_mode: entry.revisionMode,
  }
  const result: GradeResultItem = {
    index: ordinal,
    user_answer: entry.userAnswer,
    correct_answer: question.answer,
    is_correct: false,
  }

  return (
    <li className="border-b border-hairline py-[14px]">
      <div className="flex items-center gap-3">
        <CheckSquare checked={checked} onChange={onToggle} label={`选中第 ${ordinal} 条错题`} />
        <button
          type="button"
          className="flex min-w-0 flex-1 items-center gap-3 text-left"
          onClick={() => setExpanded((v) => !v)}
        >
          <span className="shrink-0 text-[11px] tracking-[0.1em] text-quiet">
            {(TYPE_LABELS[question.question_type] ?? question.question_type).toUpperCase()}
          </span>
          <span className="min-w-0 flex-1 truncate text-[15px] text-ink">{preview}</span>
          {entry.timesWrong > 1 && (
            <span className="shrink-0 text-[12px] text-accent">错 {entry.timesWrong} 次</span>
          )}
          <ChevronDown
            strokeWidth={1.5}
            className={cn(
              'size-4 shrink-0 text-quiet transition-transform',
              expanded && 'rotate-180',
            )}
          />
        </button>
        <button
          type="button"
          className="shrink-0 text-[12px] text-quiet transition-colors hover:text-accent"
          onClick={onRemove}
        >
          移出
        </button>
      </div>

      <p className="mt-1 pl-[30px] text-[12.5px] text-quiet">
        来自{' '}
        <Link
          to={`/papers/${entry.paperId}`}
          className="underline-offset-2 transition-colors hover:text-accent hover:underline"
        >
          〈{entry.paperTitle}〉
        </Link>{' '}
        · {gradedAt}
      </p>

      {expanded && (
        <div className="kk-rise mt-1 pl-[30px]">
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
