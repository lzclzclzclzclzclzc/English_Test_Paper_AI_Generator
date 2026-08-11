import { useEffect, useState } from 'react'
import { cn } from '@/lib/utils'

/**
 * 生成管线进度。后端同步返回、无 SSE（spec C），故这是「不穿帮的假进度」：
 * 渐近线爬升（永远逼近而到不了 100%，请求完成时父级卸载本组件、导航离开）
 * + 阶段权重（慢在真实耗时大头的 Parser / Reviser，Retriever / Assemble 一闪而过）
 * + 通用文案（不显示任何可被证伪的具体数字）。请求真正结束由父级 `isPending`
 * 转 false 触发卸载——因此这里只管「还在跑」时的观感。
 *
 * 样式：从左到右的流程图——每步一个方块，方块底色是从左往右延伸的进度阴影，
 * 方块内显示阶段名与百分比；方块之间用 › 连接。
 */
const STEPS = [
  { code: 'PARSER', label: '解析意图', detail: '正在理解你的出题需求', weight: 3 },
  { code: 'RETRIEVER', label: '检索题库', detail: '正在从真题库匹配候选题', weight: 1 },
  { code: 'REVISER', label: '按力度加工', detail: '正在按力度保留 / 改编 / 新出，并逐题校验', weight: 5 },
  { code: 'ASSEMBLE', label: '组卷落库', detail: '正在成卷、存入历史试卷', weight: 1 },
] as const

const TOTAL_WEIGHT = STEPS.reduce((s, x) => s + x.weight, 0)

/** 每步结束时的累计进度（0..1，最后一步落在 CEILING，永不到 1）。 */
const CEILING = 0.94
const CUMULATIVE = STEPS.reduce<number[]>((acc, s) => {
  acc.push((acc[acc.length - 1] ?? 0) + s.weight)
  return acc
}, []).map((w) => (w / TOTAL_WEIGHT) * CEILING)

const TICK_MS = 90
/** 渐近逼近系数：越接近目标越慢，制造「还差一口气」的真实感。 */
const APPROACH_K = 0.045

export function PipelineProgress() {
  const [elapsed, setElapsed] = useState(0)
  // 总进度 0..CEILING（渐近线，永远到不了 1；请求完成时组件被卸载）
  const [progress, setProgress] = useState(0)

  useEffect(() => {
    const start = performance.now()
    const timer = setInterval(() => {
      setElapsed((performance.now() - start) / 1000)
      // 朝天花板渐近爬升：progress += (CEILING - progress) * k
      setProgress((p) => p + (CEILING - p) * APPROACH_K)
    }, TICK_MS)
    return () => clearInterval(timer)
  }, [])

  // 当前进度落在哪一步：progress 与各步累计阈值比较
  const activeIndex = CUMULATIVE.findIndex((c) => progress < c)
  const currentStep = activeIndex === -1 ? STEPS.length - 1 : activeIndex
  const totalPct = Math.round(progress * 100)

  return (
    <div className="kk-rise mt-8 max-w-[52rem]">
      <div className="flex items-baseline justify-between border-b border-hairline pb-2.5">
        <span className="font-ui text-[11px] font-bold tracking-[0.14em] text-quiet">PIPELINE</span>
        <span className="font-mono text-[13px] text-muted-ink">
          {totalPct}% · {elapsed.toFixed(1)}s
        </span>
      </div>

      {/* 横向流程图：方块 › 方块 › … */}
      <div className="mt-4 flex items-stretch gap-1.5 max-md:flex-col">
        {STEPS.map((step, i) => {
          const done = i < currentStep
          const active = i === currentStep
          // 该步在总进度里的区间 [prev, cur]，用于算步内局部进度（0..1）
          const prev = i === 0 ? 0 : (CUMULATIVE[i - 1] ?? 0)
          const cur = CUMULATIVE[i] ?? CEILING
          const localRatio = done
            ? 1
            : active
              ? Math.max(0, Math.min(1, (progress - prev) / (cur - prev || 1)))
              : 0
          const pct = Math.round(localRatio * 100)
          return (
            <div key={step.code} className="flex flex-1 items-center gap-1.5 max-md:flex-none">
              <div
                className={cn(
                  'relative min-w-0 flex-1 overflow-hidden rounded-sm border',
                  active
                    ? 'border-accent'
                    : done
                      ? 'border-ink-30'
                      : 'border-hairline',
                )}
              >
                {/* 从左往右延伸的进度阴影 */}
                <div
                  className={cn(
                    'absolute inset-y-0 left-0 transition-[width] duration-300 ease-out',
                    done ? 'bg-wash opacity-70' : 'bg-wash',
                  )}
                  style={{ width: `${pct}%` }}
                />
                {/* 内容层 */}
                <div className="relative flex flex-col gap-1 px-3 py-2.5">
                  <div className="flex items-center gap-1.5">
                    <span
                      className={cn(
                        'flex size-4 shrink-0 items-center justify-center rounded-full border text-[10px] leading-none',
                        done
                          ? 'border-ink-30 text-ink'
                          : active
                            ? 'kk-pulse border-accent text-accent'
                            : 'border-ink-15 text-transparent',
                      )}
                    >
                      {done ? '✓' : '·'}
                    </span>
                    <span className="font-ui text-[9.5px] font-bold tracking-[0.12em] text-quiet">
                      {step.code}
                    </span>
                  </div>
                  <span
                    className={cn('font-ui text-[13.5px]', done || active ? 'text-ink' : 'text-quiet')}
                  >
                    {step.label}
                  </span>
                  <span
                    className={cn(
                      'font-mono text-[15px] font-bold tabular-nums',
                      active ? 'text-accent' : done ? 'text-muted-ink' : 'text-quiet',
                    )}
                  >
                    {pct}%
                  </span>
                </div>
              </div>
              {/* 步骤间连接符（末步不画；小屏隐藏） */}
              {i < STEPS.length - 1 && (
                <span aria-hidden className="shrink-0 font-ui text-[16px] text-ink-20 max-md:hidden">
                  ›
                </span>
              )}
            </div>
          )
        })}
      </div>

      {/* 当前步骤的说明文案 */}
      <p className="mt-3 font-ui text-[12.5px] leading-relaxed text-quiet">
        {STEPS[currentStep]?.detail}
      </p>
    </div>
  )
}
