/**
 * Paper.metadata 由 AI Engine 生成、后端原样透传（backend-api.md「PaperResponse」节）。
 * 契约只保证"可能出现"三个字段，形态以 ai-engine-design.md 为准：
 *   - retrieval_warnings: string[]        检索告警（后端产出的中文句子，原样展示）
 *   - retrieval_shortfall / shortfall:    Record<string, number>  各题型桶缺口
 *   - revision_failures: number[]         改写失败、fallback 回原题的题号
 * 业务代码必须容忍未知字段和形态不符——这里全部宽松解析，解析不出就静默丢弃。
 */

const TYPE_LABELS: Record<string, string> = {
  single_choice: '单项选择',
  word_form: '词形转换',
  sentence_rewriting: '句子改写',
}

const isPositiveInt = (v: unknown): v is number =>
  typeof v === 'number' && Number.isInteger(v) && v > 0

/** metadata → 面向用户的说明句子列表；没有可展示内容时返回 []。 */
export function buildPaperNotices(metadata: unknown): string[] {
  if (typeof metadata !== 'object' || metadata === null) return []
  const meta = metadata as Record<string, unknown>
  const notices: string[] = []

  // 改写 fallback：设计文档承诺 list[int]（题号）
  const failures = Array.isArray(meta.revision_failures)
    ? meta.revision_failures.filter(isPositiveInt).sort((a, b) => a - b)
    : []
  if (failures.length > 0) {
    notices.push(`第 ${failures.join('、')} 题 AI 改写未成功，已使用题库原题`)
  }

  // 题量缺口：backend-api.md 写 retrieval_shortfall，AI Engine 实现里键名是 shortfall——两个都认
  const shortfall = meta.retrieval_shortfall ?? meta.shortfall
  if (typeof shortfall === 'object' && shortfall !== null && !Array.isArray(shortfall)) {
    const parts = Object.entries(shortfall as Record<string, unknown>)
      .filter((entry): entry is [string, number] => isPositiveInt(entry[1]))
      .map(([bucket, count]) => `${TYPE_LABELS[bucket] ?? bucket}缺 ${count} 道`)
    if (parts.length > 0) notices.push(`题库题量不足：${parts.join('，')}`)
  }

  // 检索告警：后端已是成句中文，原样透传
  if (Array.isArray(meta.retrieval_warnings)) {
    for (const w of meta.retrieval_warnings) {
      if (typeof w === 'string' && w.trim() !== '') notices.push(w.trim())
    }
  }

  return notices
}
