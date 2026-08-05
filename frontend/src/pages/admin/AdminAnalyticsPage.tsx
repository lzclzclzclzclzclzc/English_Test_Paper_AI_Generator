import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { getAnalytics } from '@/api/admin'
import { useKnowledgePoints } from '@/hooks/useKnowledgePoints'
import { prettifyKp, TYPE_LABELS } from '@/lib/kp'
import { cn } from '@/lib/utils'

const ACCENT = '#c2603f'
const WEAK_THRESHOLD = 0.4

const WINDOWS = [
  { label: '近 7 天', days: 7 },
  { label: '近 30 天', days: 30 },
  { label: '全部', days: 0 },
] as const

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border border-hairline bg-wash/40 px-4 py-3">
      <div className="text-[12px] text-quiet">{label}</div>
      <div className="mt-1 text-[22px] text-ink [font-family:var(--font-display)]">{value}</div>
    </div>
  )
}

function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-md border border-hairline p-4">
      <div className="mb-2 text-[13px] text-muted-ink">{title}</div>
      {children}
    </div>
  )
}

/** 全站做题分析（全体用户画像）：做题量/正确率趋势、最薄弱考点、分题型准确率。 */
export function AdminAnalyticsPage() {
  useKnowledgePoints() // 确保考点中文名可用
  const [days, setDays] = useState(30)
  const analytics = useQuery({
    queryKey: ['admin', 'analytics', days],
    queryFn: () => getAnalytics(days),
  })

  const data = analytics.data
  const mastery = data?.site_mastery

  // 趋势数据：正确率转百分比便于阅读
  const trend = (data?.attempts_by_day ?? []).map((d) => ({
    day: d.day.slice(5), // MM-DD
    attempts: d.attempts,
    rate: d.correct_rate == null ? null : Math.round(d.correct_rate * 100),
  }))

  // 薄弱考点：中文名 + 掌握度百分比
  const weak = (mastery?.weak_kps ?? []).map((k) => ({
    name: prettifyKp(k.knowledge_point_id),
    mastery: Math.round(k.mastery * 100),
    weak: k.mastery < WEAK_THRESHOLD,
  }))

  // 分题型准确率
  const types = (data?.type_accuracy ?? []).map((t) => ({
    name: TYPE_LABELS[t.question_type] ?? t.question_type,
    accuracy: Math.round(t.accuracy * 100),
    total: t.total,
  }))

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-[20px] text-ink [font-family:var(--font-display)]">做题分析</h1>
        <div className="flex gap-1">
          {WINDOWS.map((w) => (
            <button
              key={w.days}
              onClick={() => setDays(w.days)}
              className={cn(
                'h-8 rounded-lg border px-3 text-[13px] transition-colors',
                days === w.days
                  ? 'border-accent bg-wash text-accent'
                  : 'border-hairline text-muted-ink hover:bg-tint/40',
              )}
            >
              {w.label}
            </button>
          ))}
        </div>
      </div>

      {analytics.isError && (
        <div className="flex items-center gap-3 rounded-md border border-hairline bg-wash/40 px-4 py-3">
          <p className="text-[13px] text-muted-ink">数据加载失败</p>
          <button className="text-[13px] text-accent hover:underline" onClick={() => analytics.refetch()}>
            重试
          </button>
        </div>
      )}

      {analytics.isLoading && <p className="text-[13px] text-quiet">加载中…</p>}

      {data && (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <Metric label="纳入统计作答" value={mastery?.total_attempts_considered ?? 0} />
            <Metric label="覆盖考点" value={mastery?.weak_kps.length ?? 0} />
            <Metric
              label="薄弱考点"
              value={(mastery?.weak_kps ?? []).filter((k) => k.mastery < WEAK_THRESHOLD).length}
            />
          </div>

          <ChartCard title="每日做题量 / 正确率">
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={trend}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--ink-10)" />
                <XAxis dataKey="day" tick={{ fontSize: 11 }} />
                <YAxis yAxisId="vol" allowDecimals={false} tick={{ fontSize: 11 }} width={32} />
                <YAxis
                  yAxisId="rate"
                  orientation="right"
                  domain={[0, 100]}
                  tick={{ fontSize: 11 }}
                  width={36}
                  unit="%"
                />
                <Tooltip />
                <Line
                  yAxisId="vol"
                  type="monotone"
                  dataKey="attempts"
                  name="做题量"
                  stroke={ACCENT}
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  yAxisId="rate"
                  type="monotone"
                  dataKey="rate"
                  name="正确率(%)"
                  stroke="var(--text-quiet)"
                  strokeWidth={2}
                  strokeDasharray="4 3"
                  dot={false}
                  connectNulls
                />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <ChartCard title="最薄弱考点（掌握度 %）">
              {weak.length === 0 ? (
                <p className="py-8 text-center text-[13px] text-quiet">暂无做题数据</p>
              ) : (
                <ResponsiveContainer width="100%" height={Math.max(160, weak.length * 30)}>
                  <BarChart data={weak} layout="vertical" margin={{ left: 8, right: 16 }}>
                    <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} unit="%" />
                    <YAxis
                      type="category"
                      dataKey="name"
                      width={140}
                      tick={{ fontSize: 11 }}
                      interval={0}
                    />
                    <Tooltip />
                    <Bar dataKey="mastery" name="掌握度(%)">
                      {weak.map((w, i) => (
                        <Cell key={i} fill={ACCENT} fillOpacity={w.weak ? 1 : 0.45} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </ChartCard>

            <ChartCard title="分题型准确率（%）">
              {types.length === 0 ? (
                <p className="py-8 text-center text-[13px] text-quiet">暂无做题数据</p>
              ) : (
                <ResponsiveContainer width="100%" height={Math.max(160, types.length * 44)}>
                  <BarChart data={types} margin={{ left: 8, right: 16 }}>
                    <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                    <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} width={36} unit="%" />
                    <Tooltip />
                    <Bar dataKey="accuracy" name="准确率(%)" fill={ACCENT} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </ChartCard>
          </div>
        </>
      )}
    </div>
  )
}
