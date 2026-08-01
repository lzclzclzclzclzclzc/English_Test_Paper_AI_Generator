import { useMemo } from 'react'
import type { Paper } from '@/types/api'
import type { AnswerDraft } from '@/lib/answers'
import { listUnanswered } from '@/lib/answers'
import { cn } from '@/lib/utils'

interface AnswerCardProps {
  paper: Paper
  answers: Record<number, AnswerDraft>
}

/**
 * 右侧粘顶答题卡（handoff 第 5 屏）：N/12 大字 + 2px 赤陶进度条 +
 * 4 列题号方格。与试卷正文读同一份 answers，不复制第二份。
 */
export function AnswerCard({ paper, answers }: AnswerCardProps) {
  const unanswered = useMemo(() => new Set(listUnanswered(paper, answers)), [paper, answers])
  const answeredCount = paper.items.length - unanswered.size
  const ratio = paper.items.length === 0 ? 0 : answeredCount / paper.items.length

  return (
    <div className="sticky top-10 flex w-[280px] shrink-0 flex-col gap-4 max-lg:hidden">
      <span className="text-[11px] font-bold tracking-[0.14em] text-quiet">答题卡</span>
      <span className="text-[28px] leading-none text-ink">
        {answeredCount}
        <span className="text-[16px] text-quiet"> / {paper.items.length}</span>
      </span>
      <div className="h-[2px] w-full bg-ink-10">
        <div
          className="h-full bg-accent transition-[width] duration-300 ease-out"
          style={{ width: `${Math.round(ratio * 100)}%` }}
        />
      </div>
      <div className="grid grid-cols-4 gap-2">
        {paper.items.map((item) => {
          const done = !unanswered.has(item.index)
          return (
            <a
              key={item.index}
              href={`#q-${item.index}`}
              className={cn(
                'flex h-[34px] items-center justify-center rounded-sm border text-[13px] transition-colors',
                done
                  ? 'border-accent bg-wash text-ink'
                  : 'border-ink-15 text-quiet hover:border-ink-30',
              )}
            >
              {item.index}
            </a>
          )
        })}
      </div>
      <p className="text-[12px] leading-relaxed text-quiet">
        答案只保存在本页内存中，刷新会丢失；做完记得提交判分。
      </p>
    </div>
  )
}
