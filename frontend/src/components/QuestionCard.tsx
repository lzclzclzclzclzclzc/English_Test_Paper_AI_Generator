import type { ReactNode } from 'react'
import type { GradeResultItem, PaperItem } from '@/types/api'
import type { AnswerDraft, BlankMap } from '@/lib/answers'
import { formatCorrectAnswer, formatUserAnswer } from '@/lib/answers'
import { SingleChoiceField } from '@/components/question-fields/SingleChoiceField'
import { ListeningSingleChoiceField } from '@/components/question-fields/ListeningSingleChoiceField'
import { WordFormField } from '@/components/question-fields/WordFormField'
import { SentenceRewritingField } from '@/components/question-fields/SentenceRewritingField'
import { prettifyKp } from '@/lib/kp'
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

/** 单题渲染：题号行 + 题型分派 + review 态的答案比对/解析。 */
export function QuestionCard({
  item,
  mode,
  value,
  onChange,
  result,
  solutionSlot,
}: QuestionCardProps) {
  useKnowledgePoints()  // 目录到达后重渲染，考点标签显示为中文名
  const { question } = item
  const isReview = mode === 'review'

  return (
    <div className="flex gap-3 py-6">
      {/* 题号列：review 态前缀 ✓/✗ */}
      <div className="flex w-10 shrink-0 flex-col items-end gap-0.5 pt-0.5">
        {isReview && result && (
          <span
            className={cn(
              'font-question text-base font-black leading-none',
              result.is_correct ? 'text-correct' : 'text-wrong',
            )}
          >
            {result.is_correct ? '✓' : '✗'}
          </span>
        )}
        <span className="text-sm font-medium text-text-mid">{item.index}.</span>
      </div>

      <div className="flex min-w-0 flex-1 flex-col gap-3">
        {question.question_type === 'single_choice' ? (
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
        ) : question.question_type === 'word_form' ? (
          <WordFormField
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

        {/* review 态：答错时的答案比对（单选已在选项上高亮，不重复） */}
        {isReview && result && !result.is_correct && question.question_type !== 'single_choice' && question.question_type !== 'listening_single_choice' && (
          <div className="flex flex-col gap-0.5 text-[13px]">
            <p className="text-wrong">
              你的答案：<span className="line-through">{formatUserAnswer(result.user_answer)}</span>
            </p>
            <p className="font-bold text-correct">
              正确答案：{formatCorrectAnswer(result.correct_answer)}
            </p>
          </div>
        )}

        {/* review 态附注：考点标签（答题态不显示，避免提示答案）+ AI 改写降级说明 */}
        {isReview && question.knowledge_point_ids.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {question.knowledge_point_ids.map((kp) => (
              <span
                key={kp}
                title={kp}
                className="rounded-full border border-line-strong px-2 py-0.5 text-[11px] text-text-mid"
              >
                {prettifyKp(kp)}
              </span>
            ))}
          </div>
        )}

        {solutionSlot}
      </div>
    </div>
  )
}
