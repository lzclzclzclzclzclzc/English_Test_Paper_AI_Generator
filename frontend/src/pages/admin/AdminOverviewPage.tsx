import { useQuery } from '@tanstack/react-query'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { getOverview, getTimeseries } from '@/api/admin'

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border border-hairline bg-wash/40 px-4 py-3">
      <div className="text-[12px] text-quiet">{label}</div>
      <div className="mt-1 font-ui text-[22px] font-bold tabular-nums text-ink">{value}</div>
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
        <Metric label="活跃会员" value={o?.active_members ?? '暂不可用'} />
        <Metric label="试卷总数" value={o?.total_papers ?? '—'} />
      </div>
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
                <Line type="monotone" dataKey="count" stroke="#c2603f" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        ))}
      </div>
    </div>
  )
}
