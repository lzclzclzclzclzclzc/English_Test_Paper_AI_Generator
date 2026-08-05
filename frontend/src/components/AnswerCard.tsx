import { useMemo } from 'react'
import type { GradeResultItem, Paper } from '@/types/api'
import type { AnswerDraft } from '@/lib/answers'
import { listUnanswered } from '@/lib/answers'
import { TYPE_LABELS } from '@/lib/kp'
import { cn } from '@/lib/utils'

interface AnswerCardProps {
  paper: Paper
  answers: Record<number, AnswerDraft>
  /** 传入判分结果即进入复盘态：题号格标注对错，隐藏作答提示 */
  results?: Map<number, GradeResultItem> | null
}

/** 本卷题型分布：卡底部的元信息行 */
function useTypeCounts(paper: Paper) {
  return useMemo(() => {
    const counts = new Map<string, number>()
    for (const item of paper.items) {
      const key = item.question.question_type
      counts.set(key, (counts.get(key) ?? 0) + 1)
    }
    return [...counts.entries()]
  }, [paper])
}

/**
 * 右侧粘顶答题卡（2026-08 卡片化改版）：卡片容器 + N/12 大字 +
 * 2px 赤陶进度条 + 4 列题号方格 + 题型分布元信息。
 * 作答态标注已答/未答；复盘态标注对/错。与试卷正文读同一份 answers。
 */
export function AnswerCard({ paper, answers, results }: AnswerCardProps) {
  const isReview = !!results
  const unanswered = useMemo(() => new Set(listUnanswered(paper, answers)), [paper, answers])
  const typeCounts = useTypeCounts(paper)

  const doneCount = isReview
    ? paper.items.filter((i) => results.get(i.index)?.is_correct).length
    : paper.items.length - unanswered.size
  const ratio = paper.items.length === 0 ? 0 : doneCount / paper.items.length

  return (
    <div className="sticky top-10 w-[280px] shrink-0 self-start max-lg:hidden">
      <div className="flex flex-col gap-4 rounded-[var(--radius-question-card)] border border-soft bg-card-surface p-5 font-ui">
        <span className="text-[11px] font-bold tracking-[0.14em] text-quiet">
          {isReview ? '本卷回顾' : '答题卡'}
        </span>
        <span className="text-[28px] leading-none text-ink">
          {doneCount}
          <span className="text-[15px] text-quiet">
            {' '}/ {paper.items.length} {isReview ? '答对' : '已答'}
          </span>
        </span>
        <div className="h-[2px] w-full bg-ink-10">
          <div
            className="h-full bg-accent transition-[width] duration-300 ease-out"
            style={{ width: `${Math.round(ratio * 100)}%` }}
          />
        </div>
        <div className="grid grid-cols-4 gap-2">
          {paper.items.map((item) => {
            const state = isReview
              ? results.get(item.index)?.is_correct
                ? 'correct'
                : 'wrong'
              : unanswered.has(item.index)
                ? 'todo'
                : 'done'
            return (
              <a
                key={item.index}
                href={`#q-${item.index}`}
                className={cn(
                  'flex h-8 items-center justify-center rounded-md border text-[13px] tabular-nums transition-colors',
                  state === 'done' && 'border-accent bg-wash text-ink',
                  state === 'todo' && 'border-ink-15 text-quiet hover:border-ink-30',
                  state === 'correct' && 'border-ink-20 text-ink',
                  state === 'wrong' && 'border-accent bg-wash text-accent',
                )}
              >
                {item.index}
              </a>
            )
          })}
        </div>

        <div className="flex flex-col gap-1 border-t border-hairline pt-4">
          <div className="flex items-baseline justify-between text-[12.5px]">
            <span className="text-quiet">题量</span>
            <span className="text-ink">{paper.items.length} 题</span>
          </div>
          {typeCounts.map(([type, count]) => (
            <div key={type} className="flex items-baseline justify-between text-[12.5px]">
              <span className="text-quiet">{TYPE_LABELS[type] ?? type}</span>
              <span className="text-ink">{count} 题</span>
            </div>
          ))}
        </div>

        {!isReview && (
          <p className="text-[12px] leading-relaxed text-quiet">
            答案只保存在本页内存中，刷新会丢失；做完记得提交判分。
          </p>
        )}
      </div>
    </div>
  )
}
