import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronDown } from 'lucide-react'
import type { GradeResultItem, PaperItem } from '@/types/api'
import type { WrongBookEntry } from '@/lib/wrongBook'
import { FAMILY_LABELS, TYPE_FAMILY, TYPE_LABELS, type TypeFamily } from '@/lib/kp'
import { PATHS } from '@/lib/paths'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { QuestionCard } from '@/components/QuestionCard'
import { SolutionBlock } from '@/components/SolutionBlock'

interface WrongBookListProps {
  entries: WrongBookEntry[]
  selected: Set<string>
  onToggle: (sourceQuestionId: string) => void
  /** 全选当前过滤视图内的错题（并集，不影响其他分类下已有的勾选） */
  onSelectMany: (sourceQuestionIds: string[]) => void
  onClearSelection: () => void
  onRemove: (sourceQuestionId: string) => void
  /** 解析配额用（与试卷页共享每日次数） */
  locked: boolean
  userId: string
}

/** 族色题型标签（配色抄 QuestionCard FAMILY_PILL：wash 底 + 同色字，方角小 chip） */
const FAMILY_PILL: Record<TypeFamily, string> = {
  grammar: 'bg-grammar-wash text-grammar',
  listening: 'bg-listening-wash text-listening',
  reading: 'bg-reading-wash text-reading',
}

const FAMILY_ORDER: readonly TypeFamily[] = ['grammar', 'listening', 'reading']

const familyOf = (entry: WrongBookEntry): TypeFamily =>
  TYPE_FAMILY[entry.question.question_type] ?? 'grammar'

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
        'flex size-[18px] shrink-0 items-center justify-center rounded-sm border font-ui text-[11px] leading-none transition-colors',
        checked ? 'border-accent bg-wash text-accent' : 'border-ink-20 text-transparent hover:border-ink-30',
      )}
    >
      ✓
    </button>
  )
}

/** 过滤芯片：选中 = 赤陶边 + wash 底（同掌握度页统计窗口分段）。 */
function FilterChip({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        'rounded-sm border px-2.5 py-1 font-ui text-[12.5px] leading-none tabular-nums transition-colors',
        active
          ? 'border-accent bg-wash text-ink'
          : 'border-hairline text-muted-ink hover:bg-tint hover:text-ink',
      )}
    >
      {children}
    </button>
  )
}

/**
 * 错题列表（错题本页左列）：过滤芯片行（按题型三族计数）+ 全选/清空小操作行 +
 * divide-y 错题行——勾选、展开复看、请求解析、移除。数据逻辑不变，仅重排版。
 */
export function WrongBookList({
  entries,
  selected,
  onToggle,
  onSelectMany,
  onClearSelection,
  onRemove,
  locked,
  userId,
}: WrongBookListProps) {
  const [family, setFamily] = useState<'all' | TypeFamily>('all')

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

  const counts: Record<TypeFamily, number> = { grammar: 0, listening: 0, reading: 0 }
  for (const entry of entries) counts[familyOf(entry)] += 1
  // 当前族的错题被移光时芯片会消失，回退到「全部」
  const activeFamily = family !== 'all' && counts[family] === 0 ? 'all' : family
  const filtered =
    activeFamily === 'all' ? entries : entries.filter((e) => familyOf(e) === activeFamily)

  return (
    <div className="flex flex-col gap-3">
      {/* 过滤芯片行：全部 + 有错题的族（空族不显示） */}
      <div className="flex flex-wrap items-center gap-2">
        <FilterChip active={activeFamily === 'all'} onClick={() => setFamily('all')}>
          全部 {entries.length}
        </FilterChip>
        {FAMILY_ORDER.filter((f) => counts[f] > 0).map((f) => (
          <FilterChip key={f} active={activeFamily === f} onClick={() => setFamily(f)}>
            {FAMILY_LABELS[f]} {counts[f]}
          </FilterChip>
        ))}
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

      <ul className="divide-y divide-ink-10 border-y border-hairline">
        {filtered.map((entry, i) => (
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
                locked={locked}
                userId={userId}
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
