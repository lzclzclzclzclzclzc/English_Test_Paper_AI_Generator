import { useEffect, useState } from 'react'
import { cn } from '@/lib/utils'

/**
 * 生成管线进度（handoff 第 4 屏）。后端同步返回、无 SSE（spec C 明确），
 * 分步进度按固定时间轴演示（handoff 落地方式 a：假进度 + 真耗时）；
 * 请求真正完成时父级导航离开、本组件卸载。
 */
const STEPS = [
  {
    name: 'Parser · 解析意图',
    detail: '现在完成时 · single_choice · 12 题 · 难度 medium · revision_intensity=light',
    duration: 0.8,
  },
  {
    name: 'Retriever · 检索题库',
    detail: '硬过滤 214 题 ∩ 向量 Top-60 → 命中 31 题｜《语法专项突破》第 7 章、《三年真题》2023 卷',
    duration: 1.2,
  },
  {
    name: 'Reviser · 按力度加工',
    detail: '原题 4 · 轻改 6 · 新出 2；1 题校验未过已回落原题',
    duration: 2.6,
  },
  {
    name: 'Assemble · 组卷落库',
    detail: '写入 papers 表，payload 18 KB',
    duration: 0.3,
  },
] as const

const CUMULATIVE = STEPS.reduce<number[]>((acc, s) => {
  acc.push((acc[acc.length - 1] ?? 0) + s.duration)
  return acc
}, [])

export function PipelineProgress() {
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    const start = performance.now()
    const timer = setInterval(() => setElapsed((performance.now() - start) / 1000), 100)
    return () => clearInterval(timer)
  }, [])

  return (
    <div className="kk-rise mt-8 max-w-[44rem]">
      <div className="flex items-baseline justify-between border-b border-hairline pb-2.5">
        <span className="text-[11px] font-bold tracking-[0.14em] text-quiet">PIPELINE</span>
        <span className="font-mono text-[13px] text-muted-ink">{elapsed.toFixed(1)}s</span>
      </div>
      <div className="flex flex-col">
        {STEPS.map((step, i) => {
          const done = elapsed >= (CUMULATIVE[i] ?? Infinity)
          const active = !done && (i === 0 || elapsed >= (CUMULATIVE[i - 1] ?? Infinity))
          return (
            <div
              key={step.name}
              className="grid grid-cols-[22px_minmax(0,1fr)_auto] items-start gap-x-2 border-b border-hairline py-3.5 last:border-b-0"
            >
              {/* 状态圆点：完成 ✓ 墨色边 / 进行中 赤陶脉冲 / 未开始 弱边 */}
              <span
                className={cn(
                  'mt-0.5 flex size-4 items-center justify-center rounded-full border text-[10px] leading-none',
                  done
                    ? 'border-ink-30 text-ink'
                    : active
                      ? 'kk-pulse border-accent text-accent'
                      : 'border-ink-15 text-transparent',
                )}
              >
                {done ? '✓' : '·'}
              </span>
              <div className="flex min-w-0 flex-col gap-1">
                <span className={cn('text-[14px]', done || active ? 'text-ink' : 'text-quiet')}>
                  {step.name}
                </span>
                {(done || active) && (
                  <span className="text-[12px] leading-relaxed text-quiet">{step.detail}</span>
                )}
                <div className="mt-1 h-[2px] w-full overflow-hidden bg-ink-10">
                  <div
                    className={cn('h-full bg-accent transition-[width] duration-300 ease-out', done && 'opacity-55')}
                    style={{ width: done ? '100%' : active ? '55%' : '0%' }}
                  />
                </div>
              </div>
              <span className="mt-0.5 font-mono text-[12px] text-quiet">
                {done ? `${step.duration.toFixed(1)}s` : ''}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
