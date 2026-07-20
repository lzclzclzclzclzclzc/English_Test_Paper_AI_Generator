import type { ReactNode } from 'react'

interface PaperSheetProps {
  title: string
  /** 卷头下方的 meta 行（题数 / 满分 / 生成时间） */
  meta: string
  /** 右上角分数章等叠加物（成绩视图） */
  stamp?: ReactNode
  children: ReactNode
}

/**
 * 卷面外壳（Spec F § 4 卷面语言）：直角白纸 + 装订线 + 文武线卷头。
 * 做题/成绩两视图共用；卷面元素只出现在这层内部。
 */
export function PaperSheet({ title, meta, stamp, children }: PaperSheetProps) {
  return (
    <div className="relative border border-line bg-sheet shadow-[0_1px_4px_rgba(44,42,36,.05)]">
      {/* 装订线：左侧 22px 竖虚线 + 竖排小字（纯装饰） */}
      <div
        aria-hidden
        className="absolute inset-y-0 left-[22px] border-l border-dashed border-[#c9c2b2]"
      />
      <span
        aria-hidden
        className="absolute left-[6px] top-1/2 -translate-y-1/2 select-none text-[10px] tracking-[6px] text-[#c9c2b2] [writing-mode:vertical-rl]"
      >
        装订线内不要答题
      </span>

      {stamp}

      <div className="py-10 pl-14 pr-10">
        {/* 双线卷头（文武线） */}
        <div className="flex flex-col items-center gap-3">
          <h1 className="text-center font-serif text-2xl font-black tracking-[2px] text-foreground">
            {title}
          </h1>
          <div className="w-[200px] border-b border-t-2 border-foreground pb-[3px]" />
          <p className="text-xs text-muted-foreground">{meta}</p>
        </div>

        <div className="mt-8">{children}</div>
      </div>
    </div>
  )
}
