import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { getOverview, getSystemHealth, getTimeseries } from '@/api/admin'
import { formatYuan } from '@/lib/money'
import { cn } from '@/lib/utils'

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border border-hairline bg-wash/40 px-4 py-3">
      <div className="text-[12px] text-quiet">{label}</div>
      <div className="mt-1 font-ui text-[22px] font-bold tabular-nums text-ink">{value}</div>
    </div>
  )
}

/** 系统健康折叠区块（Spec H D4）：payment/LLM 探活 + 题库/数据库概况。 */
function SystemHealthPanel() {
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
      <button
        className="flex w-full items-center justify-between px-4 py-3 text-left"
        onClick={() => setOpen((v) => !v)}
      >
        <span className="text-[14px] text-ink">系统健康</span>
        <span className="text-[12px] text-quiet">{open ? '收起' : '展开'}</span>
      </button>
      {open && (
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-hairline px-4 py-3">
          {health.isLoading && <span className="text-[13px] text-quiet">检测中…</span>}
          {health.isError && (
            <span className="text-[13px] text-muted-ink">
              检测失败{' '}
              <button className="text-accent hover:underline" onClick={() => health.refetch()}>
                重试
              </button>
            </span>
          )}
          {health.data && (
            <>
              <Badge ok={health.data.payment} label="支付服务 " />
              <Badge ok={health.data.llm} label="LLM 服务 " />
              <span className="text-[13px] text-muted-ink">题库 {health.data.question_bank_total} 题</span>
              <span className="text-[13px] text-muted-ink">
                用户库 {health.data.app_db_size_kb.toLocaleString()} KB
              </span>
            </>
          )}
        </div>
      )}
    </div>
  )
}

export function AdminOverviewPage() {
  const overview = useQuery({ queryKey: ['admin', 'overview'], queryFn: getOverview })
  const series = useQuery({ queryKey: ['admin', 'timeseries'], queryFn: () => getTimeseries(30) })
  const o = overview.data
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-[20px] text-ink [font-family:var(--font-display)]">概览</h1>
      {(overview.isError || series.isError) && (
        <div className="flex items-center gap-3 rounded-md border border-hairline bg-wash/40 px-4 py-3">
          <p className="text-[13px] text-muted-ink">部分数据加载失败</p>
          <button
            className="text-[13px] text-accent hover:underline"
            onClick={() => { overview.refetch(); series.refetch() }}
          >
            重试
          </button>
        </div>
      )}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Metric label="总用户" value={o?.total_users ?? '—'} />
        <Metric label="今日新增" value={o?.new_users_today ?? '—'} />
        <Metric label="封禁用户" value={o?.banned_users ?? '—'} />
        <Metric label="活跃会员" value={o?.active_members ?? '暂不可用'} />
        <Metric label="试卷总数" value={o?.total_papers ?? '—'} />
        <Metric label="总做题数" value={o?.total_attempts ?? '—'} />
        <Metric
          label="累计收入"
          value={o?.total_revenue_cents == null ? '暂不可用' : formatYuan(o.total_revenue_cents)}
        />
      </div>
      <SystemHealthPanel />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {(['users_by_day', 'papers_by_day'] as const).map((key) => (
          <div key={key} className="rounded-md border border-hairline p-4">
            <div className="mb-2 text-[13px] text-muted-ink">
              {key === 'users_by_day' ? '每日新增用户' : '每日生成试卷'}
            </div>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={series.data?.[key] ?? []}>
                <XAxis dataKey="day" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} width={28} />
                <Tooltip />
                <Line type="monotone" dataKey="count" stroke="#ef4a2b" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        ))}
      </div>
    </div>
  )
}
