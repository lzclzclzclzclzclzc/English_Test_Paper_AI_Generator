import type { ReactNode } from 'react'
import type { GradeResultItem, PaperItem } from '@/types/api'
import type { AnswerDraft, BlankMap } from '@/lib/answers'
import { formatCorrectAnswer, formatUserAnswer } from '@/lib/answers'
import { SingleChoiceField } from '@/components/question-fields/SingleChoiceField'
import { ListeningSingleChoiceField } from '@/components/question-fields/ListeningSingleChoiceField'
import { ListeningTrueFalseField } from '@/components/question-fields/ListeningTrueFalseField'
import { ListeningFillBlankField } from '@/components/question-fields/ListeningFillBlankField'
import { WordFormField } from '@/components/question-fields/WordFormField'
import { SentenceRewritingField } from '@/components/question-fields/SentenceRewritingField'
import { TYPE_LABELS, prettifyKp } from '@/lib/kp'
import { useKnowledgePoints } from '@/hooks/useKnowledgePoints'
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
}

const REVISION_LABELS: Record<PaperItem['revision_mode'], string> = {
  fresh: 'FRESH 新出',
  light: 'LIGHT 轻改',
  original: 'ORIGINAL 原题',
}

/**
 * 单题（handoff 第 5 屏）：`<article>` + 底部细线；题号等宽弱色 +
 * 题型/知识点/改题档位 11px 大写标签；review 态状态圆 ✓ 墨色边 / ✕ 赤陶。
 */
export function QuestionCard({
  item,
  mode,
  value,
  onChange,
  result,
  solutionSlot,
}: QuestionCardProps) {
  useKnowledgePoints() // 目录到达后重渲染，考点标签显示为中文名
  const { question } = item
  const isReview = mode === 'review'

  const labels: string[] = [
    (TYPE_LABELS[question.question_type] ?? question.question_type).toUpperCase(),
  ]
  // 答题态不展示考点标签（避免提示答案），review 态补上
  if (isReview) {
    labels.push(...question.knowledge_point_ids.map(prettifyKp))
  }
  labels.push(REVISION_LABELS[item.revision_mode] ?? item.revision_mode)

  return (
    <article id={`q-${item.index}`} className="flex scroll-mt-10 flex-col gap-3 py-10 first:pt-6">
      <div className="flex items-center gap-3">
        {isReview && result && (
          <span
            className={cn(
              'flex size-[22px] shrink-0 items-center justify-center rounded-full border text-[12px] leading-none',
              result.is_correct ? 'border-ink-30 text-ink' : 'border-accent text-accent',
            )}
          >
            {result.is_correct ? '✓' : '✕'}
          </span>
        )}
        <span className="font-mono text-[13px] text-quiet">
          {String(item.index).padStart(2, '0')}
        </span>
        <span className="text-[11px] tracking-[0.1em] text-quiet">{labels.join(' · ')}</span>
      </div>

      <div className="flex min-w-0 flex-col gap-3">
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
        ) : (
          <SentenceRewritingField
            question={question}
            mode={mode}
            value={typeof value === 'object' ? (value as BlankMap) : undefined}
            onChange={onChange}
            result={result}
          />
        )}

        {/* review 态：答错时的答案比对（单选/听力/判断/阅读已在选项上标注，不重复） */}
        {isReview && result && !result.is_correct && question.question_type !== 'single_choice' && question.question_type !== 'listening_single_choice' && question.question_type !== 'listening_true_false' && question.question_type !== 'reading_longtext_single_choice' && question.question_type !== 'cloze_single_choice' && (
          <div className="flex flex-wrap gap-x-6 gap-y-0.5 text-[13px]">
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
