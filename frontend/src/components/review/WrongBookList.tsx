import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronDown } from 'lucide-react'
import type { GradeResultItem, PaperItem } from '@/types/api'
import type { WrongBookEntry } from '@/lib/wrongBook'
import { TYPE_FAMILY, TYPE_LABELS, type TypeFamily } from '@/lib/kp'
import { PATHS } from '@/lib/paths'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { QuestionCard } from '@/components/QuestionCard'
import { SolutionBlock } from '@/components/SolutionBlock'
import { EmptyState } from '@/components/EmptyState'

interface WrongBookListProps {
  entries: WrongBookEntry[]
  selected: Set<string>
  onToggle: (sourceQuestionId: string) => void
  /** 全选当前过滤视图内的错题（并集，不影响其他分类下已有的勾选） */
  onSelectMany: (sourceQuestionIds: string[]) => void
  onClearSelection: () => void
  onRemove: (sourceQuestionId: string) => void
}

/** 族色题型标签（配色抄 QuestionCard FAMILY_PILL：wash 底 + 同色字，方角小 chip） */
const FAMILY_PILL: Record<TypeFamily, string> = {
  grammar: 'bg-grammar-wash text-grammar',
  listening: 'bg-listening-wash text-listening',
  reading: 'bg-reading-wash text-reading',
  writing: 'bg-writing-wash text-writing',
}

/** ISO 时间戳 → 本地日历日期（YYYY-MM-DD），与错题行显示的 MM-DD 同一时区，供日期区间比较。 */
const localYmd = (iso: string) => {
  const d = new Date(iso)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

/** 勾选方块（handoff 第 9 屏）：选中 = 墨色实心 + ✓。 */
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
        'flex size-[18px] shrink-0 items-center justify-center rounded-sm border font-ui text-[11px] leading-none transition-colors',
        checked ? 'border-ink bg-ink text-paper' : 'border-ink-20 text-transparent hover:border-ink-30',
      )}
    >
      ✓
    </button>
  )
}

/**
 * 错题列表（错题本页左列）：筛选条（精确题型 Select + 日期区间）+ 全选/清空小操作行 +
 * divide-y 错题行——勾选、展开复看、请求解析、移除。数据逻辑不变，仅重排版。
 */
export function WrongBookList({
  entries,
  selected,
  onToggle,
  onSelectMany,
  onClearSelection,
  onRemove,
}: WrongBookListProps) {
  const [questionType, setQuestionType] = useState('') // '' = 全部题型
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')

  if (entries.length === 0) {
    return (
      <EmptyState
        title="错题本还是空的"
        desc="交卷后答错的题会自动收进来，随时回来复练"
        action={
          <Button asChild>
            <Link to={PATHS.dashboard}>去出一份卷</Link>
          </Button>
        }
      />
    )
  }

  const hasFilters = !!(questionType || startDate || endDate)
  const clearFilters = () => {
    setQuestionType('')
    setStartDate('')
    setEndDate('')
  }

  // 客户端筛选：题型精确匹配 + 日期区间（按本地日历日 lexicographic 比较）。
  const filtered = entries.filter((e) => {
    if (questionType && e.question.question_type !== questionType) return false
    if (startDate || endDate) {
      const day = localYmd(e.gradedAt)
      if (startDate && day < startDate) return false
      if (endDate && day > endDate) return false
    }
    return true
  })

  return (
    <div className="flex flex-col gap-3">
      {/* 筛选条：精确题型 Select + 日期区间（抄历史试卷页 FilterBar 的记法/字号/token） */}
      <div className="flex flex-wrap items-center gap-x-5 gap-y-3">
        {/* 题型 */}
        <Select
          value={questionType || 'all'}
          onValueChange={(v) => setQuestionType(v === 'all' ? '' : v)}
        >
          <SelectTrigger size="sm" aria-label="题型筛选" className="border-ink-20 font-ui text-[12.5px]">
            <SelectValue placeholder="全部题型" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部题型</SelectItem>
            {Object.entries(TYPE_LABELS).map(([type, label]) => (
              <SelectItem key={type} value={type}>
                {label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {/* 日期区间 */}
        <div className="inline-flex items-center gap-1.5 font-ui text-[12.5px] text-quiet">
          <span>起</span>
          <input
            type="date"
            value={startDate}
            max={endDate || undefined}
            aria-label="起始日期"
            onChange={(e) => setStartDate(e.target.value)}
            className="rounded-lg border border-ink-20 px-2 py-1 text-ink outline-none transition-colors focus:border-accent"
          />
          <span>止</span>
          <input
            type="date"
            value={endDate}
            min={startDate || undefined}
            aria-label="截止日期"
            onChange={(e) => setEndDate(e.target.value)}
            className="rounded-lg border border-ink-20 px-2 py-1 text-ink outline-none transition-colors focus:border-accent"
          />
        </div>

        {hasFilters && (
          <button
            type="button"
            onClick={clearFilters}
            className="font-ui text-[12.5px] text-quiet underline-offset-4 transition-colors hover:text-ink hover:underline"
          >
            清除筛选
          </button>
        )}
      </div>

      {/* 全选/清空小操作行 */}
      <div className="flex flex-wrap items-center gap-4 font-ui text-[12.5px]">
        <button
          type="button"
          className="text-muted-ink transition-colors hover:text-accent"
          onClick={() => onSelectMany(filtered.map((e) => e.sourceQuestionId))}
        >
          全选
        </button>
        <button
          type="button"
          className="text-muted-ink transition-colors hover:text-accent"
          onClick={onClearSelection}
        >
          清空勾选
        </button>
        <span className="ml-auto text-quiet tabular-nums">已选 {selected.size} 道</span>
      </div>

      {filtered.length === 0 ? (
        // 有错题但筛选把它们全排除：内联提示，筛选条保持可见以便清除。
        <div className="flex flex-col items-start gap-2 border-y border-hairline py-8">
          <p className="text-[13.5px] text-muted-ink">没有符合条件的错题</p>
          <button
            type="button"
            className="font-ui text-[12.5px] text-quiet underline-offset-4 transition-colors hover:text-ink hover:underline"
            onClick={clearFilters}
          >
            清除筛选
          </button>
        </div>
      ) : (
        <ul className="divide-y divide-ink-10 border-y border-hairline">
          {filtered.map((entry, i) => (
            <WrongBookRow
              key={`${entry.sourceQuestionId}-${entry.gradedAt}`}
              entry={entry}
              ordinal={i + 1}
              checked={selected.has(entry.sourceQuestionId)}
              onToggle={() => onToggle(entry.sourceQuestionId)}
              onRemove={() => onRemove(entry.sourceQuestionId)}
            />
          ))}
        </ul>
      )}
    </div>
  )
}

function WrongBookRow({
  entry,
  ordinal,
  checked,
  onToggle,
  onRemove,
}: {
  entry: WrongBookEntry
  ordinal: number
  checked: boolean
  onToggle: () => void
  onRemove: () => void
}) {
  const [expanded, setExpanded] = useState(false)
  const { question } = entry
  const preview = question.stem ?? question.original_sentence ?? '（无题干）'
  const graded = new Date(entry.gradedAt)
  const shortDate = `${String(graded.getMonth() + 1).padStart(2, '0')}-${String(graded.getDate()).padStart(2, '0')}`
  const fullDate = graded.toLocaleString('zh-CN', { dateStyle: 'medium', timeStyle: 'short' })

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
    <li className="py-[14px]">
      <div className="flex items-center gap-3">
        <CheckSquare checked={checked} onChange={onToggle} label={`选中第 ${ordinal} 条错题`} />
        <button
          type="button"
          className="flex min-w-0 flex-1 items-center gap-3 text-left"
          onClick={() => setExpanded((v) => !v)}
        >
          <span
            className={cn(
              'shrink-0 rounded-sm px-2 py-[3px] font-ui text-[11px] leading-none',
              FAMILY_PILL[TYPE_FAMILY[question.question_type] ?? 'grammar'],
            )}
          >
            {TYPE_LABELS[question.question_type] ?? question.question_type}
          </span>
          <span className="min-w-0 flex-1 truncate text-[15px] text-ink">{preview}</span>
          {entry.timesWrong > 1 && (
            <span className="shrink-0 font-ui text-[12px] tabular-nums text-accent">
              错 {entry.timesWrong} 次
            </span>
          )}
          <span className="shrink-0 font-ui text-[12px] tabular-nums text-quiet">{shortDate}</span>
          <ChevronDown
            strokeWidth={1.5}
            className={cn(
              'size-4 shrink-0 text-quiet transition-transform',
              expanded && 'rotate-180',
            )}
          />
        </button>
      </div>

      {expanded && (
        <div className="kk-rise mt-3 flex flex-col gap-2 pl-[30px]">
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
              />
            }
          />
          <p className="flex flex-wrap items-baseline gap-x-2 text-[12.5px] text-quiet">
            <span>
              来自{' '}
              <Link
                to={`/papers/${entry.paperId}`}
                className="underline-offset-2 transition-colors hover:text-accent hover:underline"
              >
                〈{entry.paperTitle}〉
              </Link>{' '}
              · {fullDate}
            </span>
            <button
              type="button"
              className="font-ui transition-colors hover:text-accent"
              onClick={onRemove}
            >
              移除
            </button>
          </p>
        </div>
      )}
    </li>
  )
}
