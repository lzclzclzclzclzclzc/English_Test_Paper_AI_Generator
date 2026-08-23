import type { ReactNode } from 'react'

interface PageHeaderProps {
  title: string
  /** 引导句(可含 <mark> wash 高亮),42rem 阅读宽度 */
  intro?: ReactNode
  /** 右侧控件(如掌握度页的时间窗分段按钮) */
  children?: ReactNode
}

/**
 * 应用内页头（卷王 variant-5）:30px 粗体无衬线标题 + 引导句。
 * 不设 kicker——标题是每屏第一声。
 */
export function PageHeader({ title, intro, children }: PageHeaderProps) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-x-8 gap-y-4">
      <div className="flex min-w-0 flex-col gap-2">
        <h1 className="font-heading text-[30px] font-bold leading-tight tracking-[-0.01em] text-ink [text-wrap:balance]">
          {title}
        </h1>
        {intro && (
          <p className="max-w-[42rem] text-[15px] leading-[1.9] text-muted-ink">{intro}</p>
        )}
      </div>
      {children}
    </div>
  )
}
