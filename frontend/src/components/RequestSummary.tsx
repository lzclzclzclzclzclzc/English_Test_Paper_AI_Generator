import type { GenerateRequest } from '@/types/api'
import { TYPE_LABELS, prettifyKp } from '@/lib/kp'

const MODE_LABELS: Record<GenerateRequest['mode'], string> = {
  fresh: '新生成',
  remediation: '错题巩固',
  review: '综合复习',
}

const INTENSITY_LABELS: Record<GenerateRequest['revision_intensity'], string> = {
  fresh: 'AI 全新改写',
  light: 'AI 轻度改写',
  original: '题库原题',
}

/**
 * paper.request 回显（引擎解析后的出卷参数）：让用户看到「AI 是这么理解你的需求的」。
 * 只陈述事实、不提供操作（与生成说明同一视觉语言）。
 */
export function RequestSummary({ request }: { request: GenerateRequest }) {
  const parts: string[] = [MODE_LABELS[request.mode] ?? request.mode]

  parts.push(`${request.total_questions} 题`)

  const dist = Object.entries(request.type_distribution).filter(([, n]) => n > 0)
  if (dist.length > 0) {
    parts.push(dist.map(([t, n]) => `${TYPE_LABELS[t] ?? t} ×${n}`).join('、'))
  } else if (request.question_types.length > 0) {
    parts.push(request.question_types.map((t) => TYPE_LABELS[t] ?? t).join('、'))
  }

  if (request.knowledge_points.length > 0) {
    const shown = request.knowledge_points.slice(0, 4).map(prettifyKp)
    const extra = request.knowledge_points.length - shown.length
    parts.push(`考点：${shown.join('、')}${extra > 0 ? ` 等 ${request.knowledge_points.length} 个` : ''}`)
  }

  parts.push(INTENSITY_LABELS[request.revision_intensity] ?? request.revision_intensity)

  if (request.mode === 'review' && request.review_window_days != null) {
    parts.push(`统计近 ${request.review_window_days} 天`)
  }

  return (
    <p className="text-[12.5px] leading-relaxed text-text-mid" title={request.free_text || undefined}>
      <span className="font-bold text-ink">AI 对本卷的理解：</span>
      {parts.join(' · ')}
    </p>
  )
}
