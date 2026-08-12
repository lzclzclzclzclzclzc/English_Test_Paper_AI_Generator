/** 题型 id → 中文名（契约三题型，backend-api.md）。 */
export const TYPE_LABELS: Record<string, string> = {
  single_choice: '单项选择',
  word_form: '词形转换',
  sentence_rewriting: '句子改写',
  listening_single_choice: '听力选择',
  listening_true_false: '听力判断',
  listening_fill_blank: '听力填词',
  reading_longtext_single_choice: '阅读理解',
  cloze_single_choice: '完形填空',
  reading_first_blank: '阅读首字母填空',
  writing: '英语作文',
}

/** 题型 → 分科家族（Spec F v2.2 分科色）：语法=赭黄、听力=靛蓝、阅读=墨青。 */
export type TypeFamily = 'grammar' | 'listening' | 'reading'

export const FAMILY_LABELS: Record<TypeFamily, string> = {
  grammar: '语法',
  listening: '听力',
  reading: '阅读',
}

/** 族色 chip 类(wash 底 + 同色字,永不实心填充)。GenerateForm 与专项页共用。 */
export const FAMILY_CHIP_CLASS: Record<TypeFamily, string> = {
  grammar: 'border-transparent bg-grammar-wash text-grammar hover:border-grammar',
  listening: 'border-transparent bg-listening-wash text-listening hover:border-listening',
  reading: 'border-transparent bg-reading-wash text-reading hover:border-reading',
}

/** 族色文字类(分区标题等) */
export const FAMILY_TEXT_CLASS: Record<TypeFamily, string> = {
  grammar: 'text-grammar',
  listening: 'text-listening',
  reading: 'text-reading',
}

export const TYPE_FAMILY: Record<string, TypeFamily> = {
  single_choice: 'grammar',
  word_form: 'grammar',
  sentence_rewriting: 'grammar',
  listening_single_choice: 'listening',
  listening_true_false: 'listening',
  listening_fill_blank: 'listening',
  reading_longtext_single_choice: 'reading',
  cloze_single_choice: 'reading',
  reading_first_blank: 'reading',
  // 作文属"语言表达/输出"类，与语法同族（听/读为输入类）；避免引入第四族色导致 UI 断裂
  writing: 'grammar',
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
