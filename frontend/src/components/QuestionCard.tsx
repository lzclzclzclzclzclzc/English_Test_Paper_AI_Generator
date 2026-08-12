import type { ReactNode } from 'react'
import type { GradeResultItem, PaperItem } from '@/types/api'
import type { AnswerDraft, BlankMap } from '@/lib/answers'
import { formatCorrectAnswer, formatUserAnswer } from '@/lib/answers'
import { SingleChoiceField } from '@/components/question-fields/SingleChoiceField'
import { ListeningSingleChoiceField } from '@/components/question-fields/ListeningSingleChoiceField'
import { ListeningTrueFalseField } from '@/components/question-fields/ListeningTrueFalseField'
import { ListeningFillBlankField } from '@/components/question-fields/ListeningFillBlankField'
import { ReadingFirstBlankField } from '@/components/question-fields/ReadingFirstBlankField'
import { WordFormField } from '@/components/question-fields/WordFormField'
import { SentenceRewritingField } from '@/components/question-fields/SentenceRewritingField'
import { WritingField } from '@/components/question-fields/WritingField'
import { TYPE_LABELS, TYPE_FAMILY, prettifyKp, type TypeFamily } from '@/lib/kp'
import { useKnowledgePoints } from '@/hooks/useKnowledgePoints'
import { useMembership } from '@/hooks/useMembership'
import { cn } from '@/lib/utils'

interface QuestionCardProps {
  item: PaperItem
  mode: 'answering' | 'review'
  value?: AnswerDraft
  onChange?: (v: AnswerDraft) => void
  /** review 必传：该题判分结果 */
  result?: GradeResultItem
  /** review 态注入的解析区（按需请求由父级管理） */
  solutionSlot?: ReactNode
  /** review 态：作文批改结果（仅 writing 题型使用） */
  writingGradeResult?: {
    index: number
    total_score: number
    content_score: number
    language_score: number
    organization_score: number
    word_count: number
    level: string
    content_analysis: string | null
    language_analysis: string | null
    organization_analysis: string | null
    overall_comment: string | null
    revised_version: string | null
  }
}

/** 改题档位：原题 = 中性墨、轻改 = 绿、新出 = 赤陶（AI 介入程度递增） */
const REVISION_META: Record<PaperItem['revision_mode'], { label: string; className: string }> = {
  original: { label: '原题', className: 'bg-tint text-muted-ink' },
  light: { label: '轻改', className: 'bg-success-wash text-success' },
  fresh: { label: 'AI 新出', className: 'bg-wash text-accent' },
}

/** 分科色胶囊（v2.2）：语法 = 赭黄、听力 = 靛蓝、阅读 = 墨青 */
const FAMILY_PILL: Record<TypeFamily, string> = {
  grammar: 'bg-grammar-wash text-grammar',
  listening: 'bg-listening-wash text-listening',
  reading: 'bg-reading-wash text-reading',
}

/**
 * 单题卡片（2026-08 卡片化改版）：近白卡底 + 1px 浅边 + 8px 圆角，
 * hover 轻阴影；题头 = 赤陶序号块 + 题型胶囊 + 档位色胶囊；
 * review 态右侧 ✓ 墨色 / ✕ 赤陶。
 */
export function QuestionCard({
  item,
  mode,
  value,
  onChange,
  result,
  solutionSlot,
  writingGradeResult,
}: QuestionCardProps) {
  useKnowledgePoints() // 目录到达后重渲染，考点标签显示为中文名
  const { locked } = useMembership()
  const { question } = item
  const isReview = mode === 'review'

  const typeLabel = TYPE_LABELS[question.question_type] ?? question.question_type
  const revision = REVISION_META[item.revision_mode] ?? {
    label: item.revision_mode,
    className: 'bg-tint text-muted-ink',
  }
  // 答题态不展示考点标签（避免提示答案），review 态补上
  const kpLabels = isReview ? question.knowledge_point_ids.map(prettifyKp) : []

  return (
    <article
      id={`q-${item.index}`}
      className="scroll-mt-10 rounded-[var(--radius-question-card)] border border-soft bg-card-surface p-6 transition-shadow duration-200 hover:shadow-[var(--shadow-card-hover)] max-md:p-4"
    >
      <div className="flex flex-wrap items-center gap-2 font-ui">
        <span className="flex h-7 min-w-9 items-center justify-center rounded-md bg-wash px-2 text-[13px] font-bold tabular-nums text-accent">
          {String(item.index).padStart(2, '0')}
        </span>
        <span
          className={cn(
            'rounded-full px-2.5 py-1 text-[12px] leading-none',
            FAMILY_PILL[TYPE_FAMILY[question.question_type] ?? 'grammar'],
          )}
        >
          {typeLabel}
        </span>
        <span
          className={cn('rounded-full px-2.5 py-1 text-[12px] leading-none', revision.className)}
        >
          {revision.label}
        </span>
        {kpLabels.length > 0 && (
          <span className="min-w-0 truncate text-[12px] text-quiet">{kpLabels.join(' · ')}</span>
        )}
        {isReview && result && (
          <span
            className={cn(
              'ml-auto flex size-6 shrink-0 items-center justify-center rounded-full border font-bold text-[12px] leading-none',
              result.is_correct
                ? 'border-success bg-success-wash text-success'
                : 'border-accent bg-wash text-accent',
            )}
          >
            {result.is_correct ? '✓' : '✕'}
          </span>
        )}
      </div>

      <div className="mt-4 flex min-w-0 flex-col gap-3">
        {question.question_type === 'single_choice' || question.question_type === 'reading_longtext_single_choice' || question.question_type === 'cloze_single_choice' ? (
          <SingleChoiceField
            question={question}
            mode={mode}
            value={typeof value === 'string' ? value : undefined}
            onChange={onChange}
            result={result}
          />
        ) : question.question_type === 'listening_single_choice' ? (
          <ListeningSingleChoiceField
            question={question}
            mode={mode}
            value={typeof value === 'string' ? value : undefined}
            onChange={onChange}
            result={result}
          />
        ) : question.question_type === 'listening_true_false' ? (
          <ListeningTrueFalseField
            question={question}
            mode={mode}
            value={typeof value === 'string' ? value : undefined}
            onChange={onChange}
            result={result}
          />
        ) : question.question_type === 'word_form' ? (
          <WordFormField
            question={question}
            mode={mode}
            value={typeof value === 'object' ? (value as BlankMap) : undefined}
            onChange={onChange}
            result={result}
          />
        ) : question.question_type === 'listening_fill_blank' ? (
          <ListeningFillBlankField
            question={question}
            mode={mode}
            value={typeof value === 'object' ? (value as BlankMap) : undefined}
            onChange={onChange}
            result={result}
          />
        ) : question.question_type === 'reading_first_blank' ? (
          <ReadingFirstBlankField
            question={question}
            mode={mode}
            value={typeof value === 'object' ? (value as BlankMap) : undefined}
            onChange={onChange}
            result={result}
          />
        ) : question.question_type === 'writing' ? (
          <WritingField
            question={question}
            mode={mode}
            value={typeof value === 'string' ? value : undefined}
            onChange={onChange}
            gradeResult={writingGradeResult}
            isMember={!locked}
          />
        ) : (
          <SentenceRewritingField
            question={question}
            mode={mode}
            value={typeof value === 'object' ? (value as BlankMap) : undefined}
            onChange={onChange}
            result={result}
          />
        )}

        {/* review 态：答错时的答案比对（单选/听力/判断/阅读已在选项上标注，不重复；writing无标准答案，跳过） */}
        {isReview && result && !result.is_correct && question.question_type !== 'single_choice' && question.question_type !== 'listening_single_choice' && question.question_type !== 'listening_true_false' && question.question_type !== 'reading_longtext_single_choice' && question.question_type !== 'cloze_single_choice' && question.question_type !== 'writing' && (
          <div className="flex flex-wrap gap-x-6 gap-y-1 text-[13px]">
            <span className="text-accent">
              你的答案：{formatUserAnswer(result.user_answer)}
            </span>
            <span className="text-ink">
              正确答案：<b>{formatCorrectAnswer(result.correct_answer)}</b>
            </span>
          </div>
        )}

        {solutionSlot}
      </div>
    </article>
  )
}
