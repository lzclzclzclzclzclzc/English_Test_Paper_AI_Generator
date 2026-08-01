/** 题型 id → 中文名（契约三题型，backend-api.md）。 */
export const TYPE_LABELS: Record<string, string> = {
  single_choice: '单项选择',
  word_form: '词形转换',
  sentence_rewriting: '句子改写',
  listening_single_choice: '听力选择',
  listening_true_false: '听力判断',
  reading_longtext_single_choice: '阅读理解',
  cloze_single_choice: '完形填空',
}

/**
 * 知识点 id → 中文名（level2）的运行时映射。
 * 由 useKnowledgePoints() 在 App 启动时从后端 /api/knowledge-points 填充，
 * prettifyKp 优先查这里，查不到再退回 slug 翻译。
 */
const KP_NAME_MAP: Record<string, string> = {}

/** 用后端返回的目录填充 id→中文名映射（幂等，可重复调用）。 */
export function registerKpNames(entries: { id: string; level2: string }[]): void {
  for (const e of entries) KP_NAME_MAP[e.id] = e.level2
}

/**
 * 知识点 id → 人类可读中文名。
 * 优先用后端目录的 level2 中文名；未加载到时退回把 slug 翻成半中文
 * （kp_word_form_participle → "词形转换 · participle"），避免直接暴露 id。
 */
export function prettifyKp(id: string): string {
  const mapped = KP_NAME_MAP[id]
  if (mapped) return mapped

  const slug = id.replace(/^kp_/, '')
  for (const [type, label] of Object.entries(TYPE_LABELS)) {
    if (slug.startsWith(type)) {
      const rest = slug.slice(type.length).replace(/^_/, '').replaceAll('_', ' ')
      return rest ? `${label} · ${rest}` : label
    }
  }
  return slug.replaceAll('_', ' ')
}
