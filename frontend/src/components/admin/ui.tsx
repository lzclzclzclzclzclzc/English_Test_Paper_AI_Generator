import { useState } from 'react'
import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getSystemHealth } from '@/api/admin'
import { cn } from '@/lib/utils'

/**
 * 管理端共用的小组件（原先在概览/分析/用户详情/监控看板各页重复定义）：
 * 天窗档位 + 选择器、指标卡、图表卡、系统健康折叠。
 */

/** 统计天窗档位（days=0 = 全部历史）。 */
export const WINDOWS = [
  { label: '近 7 天', days: 7 },
  { label: '近 30 天', days: 30 },
  { label: '全部', days: 0 },
] as const

/** 天窗选择按钮组。 */
export function WindowPicker({ value, onChange }: { value: number; onChange: (days: number) => void }) {
  return (
    <div className="flex gap-1">
      {WINDOWS.map((w) => (
        <button
          key={w.days}
          onClick={() => onChange(w.days)}
          className={cn(
            'h-8 rounded-lg border px-3 font-ui text-[13px] transition-colors',
            value === w.days ? 'border-accent bg-wash text-accent' : 'border-hairline text-muted-ink hover:bg-tint/40',
          )}
        >
          {w.label}
        </button>
      ))}
    </div>
  )
}

/** 指标卡：标签 + 大数字（可选 hint 小字）。 */
export function Metric({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div className="rounded-md border border-hairline bg-wash/40 px-4 py-3">
      <div className="text-[12px] text-quiet">{label}</div>
      <div className="mt-1 font-ui text-[22px] font-bold tabular-nums text-ink">{value}</div>
      {hint && <div className="mt-0.5 text-[11px] text-quiet">{hint}</div>}
    </div>
  )
}

/** 图表 / 内容卡：标题（可选 hint）+ 内容。 */
export function ChartCard({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <div className="rounded-md border border-hairline p-4">
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <div className="text-[13px] text-muted-ink">{title}</div>
        {hint && <div className="text-[11px] text-quiet">{hint}</div>}
      </div>
      {children}
    </div>
  )
}

/** 系统健康折叠区块：payment / LLM 探活 + 题库/用户库概况。 */
export function SystemHealthPanel() {
  const [open, setOpen] = useState(false)
  const health = useQuery({ queryKey: ['admin', 'system-health'], queryFn: getSystemHealth, enabled: open })
  const Badge = ({ ok, label }: { ok: boolean; label: string }) => (
    <span className="inline-flex items-center gap-1.5">
      <span className={cn('h-2 w-2 rounded-full', ok ? 'bg-emerald-500' : 'bg-red-500')} />
      <span className="text-[13px] text-muted-ink">{label}{ok ? '正常' : '不可用'}</span>
    </span>
  )
  return (
    <div className="rounded-md border border-hairline">
      <button className="flex w-full items-center justify-between px-4 py-3 text-left" onClick={() => setOpen((v) => !v)}>
        <span className="text-[14px] text-ink">系统健康</span>
        <span className="text-[12px] text-quiet">{open ? '收起' : '展开'}</span>
      </button>
      {open && (
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-hairline px-4 py-3">
          {health.isLoading && <span className="text-[13px] text-quiet">检测中…</span>}
          {health.isError && (
            <span className="text-[13px] text-muted-ink">
              检测失败{' '}
              <button className="text-accent hover:underline" onClick={() => health.refetch()}>重试</button>
            </span>
          )}
          {health.data && (
            <>
              <span className="text-[13px] text-muted-ink">支付 {health.data.payment_mock ? '离线 mock' : '支付宝沙盒'}</span>
              <Badge ok={health.data.llm} label="LLM 服务 " />
              <span className="text-[13px] text-muted-ink">题库 {health.data.question_bank_total} 题</span>
              <span className="text-[13px] text-muted-ink">用户库 {health.data.app_db_size_kb.toLocaleString()} KB</span>
            </>
          )}
        </div>
      )}
    </div>
  )
}
