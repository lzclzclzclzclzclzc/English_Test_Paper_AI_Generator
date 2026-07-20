/** 题型 id → 中文名（契约三题型，backend-api.md）。 */
export const TYPE_LABELS: Record<string, string> = {
  single_choice: '单项选择',
  word_form: '词形转换',
  sentence_rewriting: '句子改写',
}

/**
 * 后端暂无知识点名称端点，MVP 先把 id slug 尽量翻成人话：
 * kp_word_form_participle → "词形转换 · participle"。
 */
export function prettifyKp(id: string): string {
  const slug = id.replace(/^kp_/, '')
  for (const [type, label] of Object.entries(TYPE_LABELS)) {
    if (slug.startsWith(type)) {
      const rest = slug.slice(type.length).replace(/^_/, '').replaceAll('_', ' ')
      return rest ? `${label} · ${rest}` : label
    }
  }
  return slug.replaceAll('_', ' ')
}
