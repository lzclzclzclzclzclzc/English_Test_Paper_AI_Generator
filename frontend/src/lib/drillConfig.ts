import type { QuestionType } from '@/types/api'
import type { Intensity } from '@/lib/composeQuery'
import { TYPE_LABELS, type TypeFamily } from '@/lib/kp'

/**
 * 题型专项页配置:一个模板 + 10 份配置(避免多页复制漂移)。
 * 数量档位、篇/道单位、KP/主题支持、强度可选性都在这层声明,
 * DrillPageTemplate 只消费配置不写死题型逻辑。
 */
export interface DrillConfig {
  type: QuestionType
  /** 路由参数 /practice/:slug */
  slug: string
  label: string
  family: TypeFamily
  unit: '道' | '篇'
  /** 单位说明(「每篇固定 6 题」等),CountSelector 旁的 quiet 小字 */
  unitHint?: string
  countPresets: readonly number[]
  /** 单题型上限(全局 30 题上限由 validateCompose 再兜一层) */
  maxCount: number
  /** 仅语法三类有知识点细分(25/13/11 个 level2) */
  supportsKp: boolean
  /** 仅语法三类支持主题词(篇章题型 SQL 随机,主题无效,不暴露输入) */
  supportsTopic: boolean
  /** 三档可选,或锁定单档(阅读首字母固定原题) */
  intensity: { options: readonly Intensity[] } | { locked: Intensity }
  /** PageHeader 引导句 */
  intro: string
  /** 练习中心题型卡上的题库量文案(2026-08 questions.db 审计) */
  bankLabel: string
}

const THREE_TIERS = { options: ['original', 'light', 'fresh'] as const }

export const DRILL_CONFIGS: readonly DrillConfig[] = [
  {
    type: 'single_choice',
    slug: 'single-choice',
    label: TYPE_LABELS.single_choice ?? '单项选择',
    family: 'grammar',
    unit: '道',
    countPresets: [5, 10, 15],
    maxCount: 30,
    supportsKp: true,
    supportsTopic: true,
    intensity: THREE_TIERS,
    intro: '中考语法单选，606 道真题打底——时态、从句、介词、冠词，25 个考点任选专练。',
    bankLabel: '606 道真题 · 25 个考点',
  },
  {
    type: 'word_form',
    slug: 'word-form',
    label: TYPE_LABELS.word_form ?? '词形转换',
    family: 'grammar',
    unit: '道',
    countPresets: [5, 8, 12],
    maxCount: 30,
    supportsKp: true,
    supportsTopic: true,
    intensity: THREE_TIERS,
    intro: '给出提示词，写出正确形态。名词复数、动词变名词、副词转换，13 个考点。',
    bankLabel: '245 道真题 · 13 个考点',
  },
  {
    type: 'sentence_rewriting',
    slug: 'sentence-rewriting',
    label: TYPE_LABELS.sentence_rewriting ?? '句子改写',
    family: 'grammar',
    unit: '道',
    countPresets: [4, 6, 10],
    maxCount: 30,
    supportsKp: true,
    supportsTopic: true,
    intensity: THREE_TIERS,
    intro: '否定句、被动语态、感叹句、对划线部分提问——11 类改写，一空一分。',
    bankLabel: '215 道真题 · 11 个考点',
  },
  {
    type: 'listening_single_choice',
    slug: 'listening-choice',
    label: TYPE_LABELS.listening_single_choice ?? '听力选择',
    family: 'listening',
    unit: '道',
    countPresets: [3, 5, 8],
    maxCount: 10,
    supportsKp: false,
    supportsTopic: false,
    intensity: THREE_TIERS,
    intro: '听短对话选答案，AI 语音朗读，可反复播放，建议戴耳机。',
    bankLabel: '37 道真题',
  },
  {
    type: 'listening_true_false',
    slug: 'listening-true-false',
    label: TYPE_LABELS.listening_true_false ?? '听力判断',
    family: 'listening',
    unit: '篇',
    unitHint: '每篇固定 5 题',
    countPresets: [1, 2, 3],
    maxCount: 6,
    supportsKp: false,
    supportsTopic: false,
    intensity: THREE_TIERS,
    intro: '听短文判断正误，练抓关键信息。按篇出题，每篇固定 5 题。',
    bankLabel: '8 篇真题',
  },
  {
    type: 'listening_fill_blank',
    slug: 'listening-fill-blank',
    label: TYPE_LABELS.listening_fill_blank ?? '听力填词',
    family: 'listening',
    unit: '篇',
    unitHint: '每篇固定 5 题',
    countPresets: [1, 2, 3],
    maxCount: 6,
    supportsKp: false,
    supportsTopic: false,
    intensity: THREE_TIERS,
    intro: '边听边写，拼写与听力一起过关。按篇出题，每篇固定 5 题。',
    bankLabel: '8 篇真题',
  },
  {
    type: 'reading_longtext_single_choice',
    slug: 'reading',
    label: TYPE_LABELS.reading_longtext_single_choice ?? '阅读理解',
    family: 'reading',
    unit: '篇',
    unitHint: '每篇固定 6 题',
    countPresets: [1, 2, 3],
    maxCount: 5,
    supportsKp: false,
    supportsTopic: false,
    intensity: THREE_TIERS,
    intro: '长文配题，主旨题细节题都有。按篇出题，每篇固定 6 题。',
    bankLabel: '9 篇真题',
  },
  {
    type: 'cloze_single_choice',
    slug: 'cloze',
    label: TYPE_LABELS.cloze_single_choice ?? '完形填空',
    family: 'reading',
    unit: '篇',
    unitHint: '每篇固定 6 题',
    countPresets: [1, 2, 3],
    maxCount: 5,
    supportsKp: false,
    supportsTopic: false,
    intensity: THREE_TIERS,
    intro: '上下文里选词，语感与逻辑并重。按篇出题，每篇固定 6 题。',
    bankLabel: '21 篇真题',
  },
  {
    type: 'reading_first_blank',
    slug: 'first-blank',
    label: TYPE_LABELS.reading_first_blank ?? '阅读首字母填空',
    family: 'reading',
    unit: '篇',
    unitHint: '1 篇 = 1 题，含 7 个首字母空',
    countPresets: [1, 2],
    maxCount: 3,
    supportsKp: false,
    supportsTopic: false,
    // 改写极易导致 7 空答案失配,parser 侧也无条件强制 original
    intensity: { locked: 'original' },
    intro: '中考阅读最难一关:给首字母补全单词。此题型固定使用真题原文。',
    bankLabel: '31 篇真题',
  },
  {
    type: 'writing',
    slug: 'writing',
    label: TYPE_LABELS.writing ?? '英语作文',
    family: 'writing',
    unit: '道',
    unitHint: '1 道 = 1 篇作文',
    countPresets: [1, 2, 3],
    maxCount: 5,
    supportsKp: false,
    supportsTopic: false,
    // 作文题给定情境命题,改写题目意义不大;由 AI 批改评分,固定使用真题原题
    intensity: { locked: 'original' },
    intro: '按题目要求成篇写作,AI 从内容、语言、结构三维度批改评分,给出修改范文。',
    bankLabel: '31 道真题',
  },
]

export function drillBySlug(slug: string): DrillConfig | undefined {
  return DRILL_CONFIGS.find((c) => c.slug === slug)
}

export function drillByType(type: QuestionType): DrillConfig | undefined {
  return DRILL_CONFIGS.find((c) => c.type === type)
}

/** 按族分组(练习中心分色分区用),顺序:语法 → 听力 → 阅读 → 写作。 */
export const DRILL_FAMILIES: ReadonlyArray<{ family: TypeFamily; configs: readonly DrillConfig[] }> =
  (['grammar', 'listening', 'reading', 'writing'] as const).map((family) => ({
    family,
    configs: DRILL_CONFIGS.filter((c) => c.family === family),
  }))

/**
 * 薄尾知识点(题量 < 8,2026-08 questions.db 审计):
 * 选中时 KpPicker 加「题量少」角注,原样强度容易凑不齐(shortfall 由
 * paperNotices 事后如实呈现,这里是事前预警,双保险)。
 */
export const THIN_KP_IDS: ReadonlySet<string> = new Set([
  'kp_sc_object_clause', // 0 题
  'kp_sc_misc', // 2
  'kp_sr_to_complex', // 3
  'kp_wf_noun_to_noun', // 3
  'kp_sc_imperative', // 4
  'kp_sr_exclamation', // 6
  'kp_sc_numerals', // 7
  'kp_sc_tag_question', // 7
  'kp_wf_degree', // 7
])

/** 零题量知识点:直接不进 KP 选择器(选了必然空手而归)。 */
export const HIDDEN_KP_IDS: ReadonlySet<string> = new Set(['kp_sc_object_clause'])
