import { useState, useMemo, useEffect } from 'react'
import type { RevisedQuestion } from '@/types/api'

interface WritingFieldProps {
  question: RevisedQuestion
  mode: 'answering' | 'review'
  value?: string
  onChange?: (v: string) => void
  /** review 态下显示批改结果 */
  gradeResult?: {
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

/**
 * 英语作文答题组件：题目 + 输入框 + 词数统计 + 提交按钮。
 * review 态：只读展示作文内容 + 批改结果（分数表 + 三维详细评析；批改按篇扣积分）。
 */
export function WritingField({
  question,
  mode,
  value,
  onChange,
  gradeResult,
}: WritingFieldProps) {
  const [text, setText] = useState(value ?? '')

  // 外部 value（历史回填）更新时同步到本地 state
  useEffect(() => {
    if (value !== undefined && value !== text) {
      setText(value)
    }
    // 仅当 value（外部引用）变化时同步，不随 text 变化触发
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value])

  // review 模式下直接用外部 value，确保 answers 回填实时生效
  const displayText = mode === 'review' ? (value ?? '') : text

  const wordCount = useMemo(() => {
    if (!displayText.trim()) return 0
    return displayText.trim().split(/\s+/).length
  }, [displayText])

  const minWords = question.min_words ?? 60
  const isBelowMin = wordCount > 0 && wordCount < minWords

  if (mode === 'review') {
    return (
      <div className="space-y-4">
        {/* 题目信息 */}
        <div className="space-y-2">
          {question.stem && (
            <h3 className="text-[17px] font-medium text-ink">{question.stem}</h3>
          )}
          {question.instruction && (
            <p className="text-[14px] text-quiet">{question.instruction}</p>
          )}
          {question.hint && (
            <div className="rounded-sm border border-hairline bg-wash px-3 py-2">
              <p className="text-[13px] leading-[1.8] text-ink">{question.hint}</p>
            </div>
          )}
          {question.reference_expressions && (
            <p className="text-[12.5px] text-quiet">
              参考表达：{question.reference_expressions}
            </p>
          )}
        </div>

        {/* 用户作文 */}
        <div className="rounded-md border border-hairline bg-wash p-4">
          <pre className="whitespace-pre-wrap font-sans text-[15px] leading-[1.8] text-ink">
            {displayText || '（未作答）'}
          </pre>
        </div>
        <p className="text-[12px] text-quiet">词数：{wordCount}</p>

        {/* 批改结果 */}
        {gradeResult && <WritingGradeDisplay result={gradeResult} />}
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {/* 题目 */}
      <div className="space-y-2">
        {question.stem && (
          <h3 className="text-[17px] font-medium text-ink">{question.stem}</h3>
        )}
        {question.instruction && (
          <p className="text-[14px] text-quiet">{question.instruction}</p>
        )}
        {question.hint && (
          <div className="rounded-sm border border-hairline bg-wash px-3 py-2">
            <p className="text-[13px] leading-[1.8] text-ink">{question.hint}</p>
          </div>
        )}
        {question.reference_expressions && (
          <p className="text-[12.5px] text-quiet">
            参考表达：{question.reference_expressions}
          </p>
        )}
      </div>

      {/* 输入框 */}
      <textarea
        rows={10}
        value={text}
        onChange={(e) => {
          const v = e.target.value
          setText(v)
          onChange?.(v)
        }}
        placeholder="在此输入你的作文..."
        className="w-full resize-y rounded-md border border-ink-20 bg-transparent px-4 py-3 text-[15px] leading-[1.8] text-ink outline-none transition-colors placeholder:text-quiet focus:border-accent"
      />

      {/* 词数统计 */}
      <div className="flex items-center justify-between">
        <span className={`text-[13px] ${isBelowMin ? 'text-accent' : 'text-quiet'}`}>
          词数：{wordCount} / {minWords}
        </span>
        {isBelowMin && (
          <span className="text-[12px] text-accent">词数不足 {minWords} 词</span>
        )}
      </div>
    </div>
  )
}

/** 批改结果展示：总分表 + 三维详细评析（2026-08 积分制起全量可见，不再分会员）。 */
function WritingGradeDisplay({
  result,
}: {
  result: {
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
}) {
  const hasDetail = Boolean(
    result.content_analysis ||
      result.language_analysis ||
      result.organization_analysis ||
      result.overall_comment ||
      result.revised_version,
  )
  return (
    <div className="space-y-4 rounded-md border border-accent/30 bg-accent/5 p-5">
      {/* 总分 — 所有人可见 */}
      <div className="text-center">
        <h3 className="text-[28px] font-medium text-ink">
          {result.total_score} <span className="text-[18px] text-quiet">/ 20 分</span>
        </h3>
        <p className="mt-1 text-[13px] text-quiet">
          {result.level} · 词数 {result.word_count}
        </p>
      </div>

      {/* 分项得分 — 所有人可见 */}
      <div className="grid grid-cols-3 gap-3">
        <ScoreCard label="内容" score={result.content_score} max={8} />
        <ScoreCard label="语言" score={result.language_score} max={8} />
        <ScoreCard label="组织结构" score={result.organization_score} max={4} />
      </div>

      {/* 详细评析区 */}
      <div className="relative">
        <div className="space-y-3">
          {hasDetail ? (
            <>
              <Section
                title="📝 内容评析"
                content={result.content_analysis ?? '（暂无内容）'}
              />
              <Section
                title="✍️ 语言评析"
                content={result.language_analysis ?? '（暂无内容）'}
              />
              <Section
                title="🏗️ 组织结构评析"
                content={result.organization_analysis ?? '（暂无内容）'}
              />
              {result.overall_comment && (
                <Section title="🌟 总体评价" content={result.overall_comment} />
              )}
              {result.revised_version && (
                <Section title="🔧 修改范文" content={result.revised_version} />
              )}
            </>
          ) : (
            <p className="text-[13px] text-quiet">本次批改未返回详细评析。</p>
          )}
        </div>
      </div>
    </div>
  )
}

function ScoreCard({ label, score, max }: { label: string; score: number; max: number }) {
  const pct = (score / max) * 100
  return (
    <div className="rounded-sm border border-hairline p-3 text-center">
      <p className="text-[12px] text-quiet">{label}</p>
      <p className="mt-1 text-[20px] font-medium text-ink">
        {score} <span className="text-[13px] text-quiet">/ {max}</span>
      </p>
      <div className="mt-2 h-1 bg-ink-10">
        <div className="h-full bg-accent" style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

function Section({ title, content }: { title: string; content: string }) {
  return (
    <div className="rounded-md border border-hairline p-4">
      <h4 className="mb-2 text-[14px] font-medium text-ink">{title}</h4>
      <div className="whitespace-pre-wrap text-[13.5px] leading-[1.8] text-ink">
        {content}
      </div>
    </div>
  )
}