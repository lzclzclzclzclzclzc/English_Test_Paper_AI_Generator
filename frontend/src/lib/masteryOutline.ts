import type { MasteryProfile } from '@/types/api'
import { prettifyKp } from '@/lib/kp'

/** 三色 band（Spec F v2.2）：< 0.4 薄弱 / 0.4–0.7 一般 / ≥ 0.7 扎实。 */
export const bandOf = (m: number): 'weak' | 'mid' | 'solid' =>
  m < 0.4 ? 'weak' : m < 0.7 ? 'mid' : 'solid'

export const BAND_LABEL: Record<'weak' | 'mid' | 'solid', string> = {
  weak: '薄弱',
  mid: '一般',
  solid: '扎实',
}

const BAND_ORDER = ['weak', 'mid', 'solid'] as const

/**
 * 掌握情况 → Markmap 大纲（纯前端 hard code，不耗 LLM，只读）。
 * 根节点=掌握情况，下挂 薄弱/一般/扎实 三支（仅渲染有考点的支），
 * 每个考点做叶子，带正确率百分比。学情报告与管理端用户详情共用。
 */
export function masteryToOutline(profile: MasteryProfile): string {
  const grouped: Record<'weak' | 'mid' | 'solid', string[]> = { weak: [], mid: [], solid: [] }
  // weak_kps 已按 mastery 升序，分桶后各组内部自然保持从低到高
  for (const kp of profile.weak_kps) {
    grouped[bandOf(kp.mastery)].push(
      `- ${prettifyKp(kp.knowledge_point_id)}（${Math.round(kp.mastery * 100)}%）`,
    )
  }
  const lines = ['# 知识点掌握情况']
  for (const band of BAND_ORDER) {
    const items = grouped[band]
    if (items.length === 0) continue
    lines.push(`## ${BAND_LABEL[band]}（${items.length}）`, ...items)
  }
  return lines.join('\n')
}
