import { useState, useMemo, useEffect } from 'react'
import { Link } from 'react-router-dom'
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
  /** review 态下是否为会员（控制详细评析显示） */
  isMember?: boolean
}

/**
 * 英语作文答题组件：题目 + 输入框 + 词数统计 + 提交按钮。
 * review 态：只读展示作文内容 + 批改结果（分数表 + 会员专属详细评析）。
 */
export function WritingField({
  question,
  mode,
  value,
  onChange,
  gradeResult,
  isMember = false,
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
        {gradeResult && <WritingGradeDisplay result={gradeResult} isMember={isMember} />}
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

/** 批改结果展示：总分表 + 详细评析。
 *  分数与档次信息对所有用户可见；详细评析区：
 *   - 会员：直接显示
 *   - 非会员：内容正常渲染在 blur 层下，上方叠加「开通会员查看」遮罩
 *   - 后端若为非会员将 content_analysis 等字段置空，依然显示空段落 + 遮罩
 */
function WritingGradeDisplay({
  result,
  isMember,
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
  isMember: boolean
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

      {/* 详细评析区：始终渲染（即便后端已裁减掉内容也保留占位） */}
      <div className="relative">
        <div
          className={
            isMember
              ? 'space-y-3'
              : 'space-y-3 [filter:blur(6px)] [pointer-events:none] select-none'
          }
        >
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
            <div className="space-y-3">
              <Section
                title="📝 内容评析"
                content={`示例：文章围绕「感谢老师」展开，情感真挚，有具体事例支撑，但第二段落稍显平淡……`}
              />
              <Section
                title="✍️ 语言评析"
                content={`示例：语法总体规范，有2处时态错误；词汇较为基础，建议适当增加高级词汇和复合句式……`}
              />
              <Section
                title="🏗️ 组织结构评析"
                content={`示例：结构清晰，采用三段式组织；段与段之间过渡可更自然……`}
              />
              <Section
                title="🌟 总体评价"
                content={`示例：整体完成度高，情感真挚，如能在句式变化和细节描写上进一步加强，将更上一层楼。`}
              />
              <Section
                title="🔧 修改范文"
                content={`示例：Dear Teacher,

I am writing this letter to express my heartfelt gratitude to you…`}
              />
            </div>
          )}
        </div>
        {/* 非会员遮罩层 */}
        {!isMember && (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
            <div className="pointer-events-auto rounded-md border border-accent/50 bg-white/85 px-6 py-5 text-center shadow-sm backdrop-blur-sm">
              <p className="text-[14px] font-medium text-ink">
                🔒 详细批改为会员专属
              </p>
              <p className="mt-1 text-[12px] text-quiet">
                <Link to="/membership" className="text-accent underline underline-offset-2">
                  开通会员
                </Link>
                可查看内容/语言/结构三维评析
                <br />
                错误分析、总体评价与修改范文
              </p>
            </div>
          </div>
        )}
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
      <div className="mt-2 h-1 rounded-full bg-hairline">
        <div className="h-full rounded-full bg-accent" style={{ width: `${pct}%` }} />
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