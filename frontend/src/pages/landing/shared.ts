import type { MouseEvent } from 'react'

/**
 * 营销首页子组件共用的小件:改题档位 chip(与试卷页 QuestionCard 的档位色
 * 一致:原题=细线边 tint 墨字、轻改=success wash、AI 新出=accent wash)
 * 与锚点平滑滚动。
 */
export type RevisionTier = 'original' | 'light' | 'fresh'

export const TIER_LABELS: Record<RevisionTier, string> = {
  original: '原题',
  light: '轻改',
  fresh: 'AI 新出',
}

/** 只含颜色,不含 border 宽度——使用处统一加 `border` + 圆角/字号。 */
export const TIER_CHIP_CLASS: Record<RevisionTier, string> = {
  original: 'border-hairline bg-tint text-ink',
  light: 'border-transparent bg-success-wash text-success',
  fresh: 'border-transparent bg-wash text-accent',
}

/** 页内锚点平滑滚动(各 section 自带 scroll-mt-20);reduced-motion 时直接跳。 */
export function scrollToAnchor(e: MouseEvent<HTMLAnchorElement>, id: string): void {
  const el = document.getElementById(id)
  if (!el) return
  e.preventDefault()
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  el.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' })
}
