import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Search, X } from 'lucide-react'
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
import { getUserAnalytics, getUserDetail, getUserMastery, listUsers } from '@/api/admin'
import { useKnowledgePoints } from '@/hooks/useKnowledgePoints'
import { prettifyKp, TYPE_LABELS } from '@/lib/kp'
import { cn } from '@/lib/utils'
import { Input } from '@/components/ui/input'
import type { AdminUserListItem } from '@/types/api'

const ACCENT = '#ef4a2b'
const WEAK_THRESHOLD = 0.4
const SEARCH_DEBOUNCE_MS = 300

const WINDOWS = [
  { label: '近 7 天', days: 7 },
  { label: '近 30 天', days: 30 },
  { label: '全部', days: 0 },
] as const

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border border-hairline bg-wash/40 px-4 py-3">
      <div className="text-[12px] text-quiet">{label}</div>
      <div className="mt-1 font-ui text-[22px] font-bold tabular-nums text-ink">{value}</div>
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

/** 搜索 + 下拉选择单个用户；选中后回调（null = 清除选择）。 */
function UserPicker({
  selected,
  onSelect,
}: {
  selected: AdminUserListItem | null
  onSelect: (u: AdminUserListItem | null) => void
}) {
  const [q, setQ] = useState('')
  const [debounced, setDebounced] = useState('')
  const [open, setOpen] = useState(false)
  const boxRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const t = setTimeout(() => setDebounced(q.trim()), SEARCH_DEBOUNCE_MS)
    return () => clearTimeout(t)
  }, [q])

  // 点击面板外关闭下拉
  useEffect(() => {
    const onDocClick = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [])

  const results = useQuery({
    queryKey: ['admin', 'learner', 'search', debounced],
    queryFn: () => listUsers(debounced, 20),
    enabled: open && !!debounced,
  })

  return (
    <div ref={boxRef} className="relative w-72">
      <div className="relative">
        <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-quiet" />
        <Input
          className="h-9 pl-8 pr-8 font-ui text-[13px]"
          placeholder="搜索用户名…"
          value={selected ? selected.username : q}
          disabled={!!selected}
          onChange={(e) => {
            setQ(e.target.value)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
        />
        {selected && (
          <button
            aria-label="清除选择"
            className="absolute right-2 top-1/2 -translate-y-1/2 text-quiet hover:text-ink"
            onClick={() => {
              onSelect(null)
              setQ('')
              setOpen(false)
            }}
          >
            <X className="size-4" />
          </button>
        )}
      </div>
      {open && !selected && debounced && (
        <div className="absolute z-20 mt-1 max-h-72 w-full overflow-auto rounded-md border border-hairline bg-paper shadow-sm">
          {results.isLoading && <p className="px-3 py-2 text-[13px] text-quiet">搜索中…</p>}
          {results.isError && (
            <button
              className="w-full px-3 py-2 text-left text-[13px] text-accent hover:underline"
              onClick={() => results.refetch()}
            >
              搜索失败，点击重试
            </button>
          )}
          {results.data && results.data.items.length === 0 && (
            <p className="px-3 py-2 text-[13px] text-quiet">没有匹配的用户</p>
          )}
          {results.data?.items.map((u) => (
            <button
              key={u.id}
              className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left hover:bg-tint/40"
              onClick={() => {
                onSelect(u)
                setOpen(false)
              }}
            >
              <span className="flex items-center gap-2">
                <span className="font-ui text-[13px] text-ink">{u.username}</span>
                {u.status === 'banned' && (
                  <span className="rounded-sm border border-hairline px-1 font-ui text-[11px] text-muted-ink">
                    已封禁
                  </span>
                )}
              </span>
              <span className="font-ui text-[12px] text-quiet">{u.attempt_count} 题</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

/** 学情页：搜索选择单个用户，展示其做题趋势、掌握度、分题型准确率。 */
export function AdminLearnerPage() {
  useKnowledgePoints() // 确保考点中文名可用
  const [selected, setSelected] = useState<AdminUserListItem | null>(null)
  const [days, setDays] = useState(30)
  const userId = selected?.id ?? null

  const detail = useQuery({
    queryKey: ['admin', 'learner', userId, 'detail'],
    queryFn: () => getUserDetail(userId!),
    enabled: !!userId,
  })
  const mastery = useQuery({
    queryKey: ['admin', 'user', userId, 'mastery'],
    queryFn: () => getUserMastery(userId!),
    enabled: !!userId,
  })
  const analytics = useQuery({
    queryKey: ['admin', 'learner', userId, 'analytics', days],
    queryFn: () => getUserAnalytics(userId!, days),
    enabled: !!userId,
  })

  const trend = useMemo(
    () =>
      (analytics.data?.attempts_by_day ?? []).map((d) => ({
        day: d.day.slice(5), // MM-DD
        attempts: d.attempts,
        rate: d.correct_rate == null ? null : Math.round(d.correct_rate * 100),
      })),
    [analytics.data],
  )
  const weak = useMemo(
    () =>
      (mastery.data?.weak_kps ?? []).map((k) => ({
        name: prettifyKp(k.knowledge_point_id),
        mastery: Math.round(k.mastery * 100),
        weak: k.mastery < WEAK_THRESHOLD,
      })),
    [mastery.data],
  )
  const types = useMemo(
    () =>
      (analytics.data?.type_accuracy ?? []).map((t) => ({
        name: TYPE_LABELS[t.question_type] ?? t.question_type,
        accuracy: Math.round(t.accuracy * 100),
        total: t.total,
      })),
    [analytics.data],
  )

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-[20px] text-ink [font-family:var(--font-display)]">学情</h1>
        <div className="flex items-center gap-3">
          <UserPicker selected={selected} onSelect={setSelected} />
          {selected && (
            <div className="flex gap-1">
              {WINDOWS.map((w) => (
                <button
                  key={w.days}
                  onClick={() => setDays(w.days)}
                  className={cn(
                    'h-8 rounded-lg border px-3 font-ui text-[13px] transition-colors',
                    days === w.days
                      ? 'border-accent bg-wash text-accent'
                      : 'border-hairline text-muted-ink hover:bg-tint/40',
                  )}
                >
                  {w.label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {!selected && (
        <p className="py-12 text-center text-[13px] text-quiet">
          输入用户名搜索并选择用户，查看其做题分析、掌握度等学情信息。
        </p>
      )}

      {selected && (
        <>
          <div className="flex items-center gap-2">
            <span className="font-ui text-[14px] text-ink">{selected.username}</span>
            <Link
              to={`/admin/users/${selected.id}`}
              className="font-ui text-[12.5px] text-accent hover:underline"
            >
              查看用户详情 →
            </Link>
          </div>

          {(detail.isLoading || analytics.isLoading || mastery.isLoading) && (
            <p className="text-[13px] text-quiet">加载中…</p>
          )}

          {detail.data && (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Metric label="试卷数" value={detail.data.paper_count} />
              <Metric label="做题数" value={detail.data.attempt_count} />
              <Metric
                label="总正确率"
                value={
                  detail.data.correct_rate == null
                    ? '—'
                    : `${Math.round(detail.data.correct_rate * 100)}%`
                }
              />
              <Metric label="纳入统计作答" value={mastery.data?.total_attempts_considered ?? '—'} />
            </div>
          )}

          {mastery.data && mastery.data.dominant_types.length > 0 && (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[13px] text-muted-ink">错误最多题型：</span>
              {mastery.data.dominant_types.map((t) => (
                <span
                  key={t}
                  className="rounded-sm border border-hairline bg-wash/60 px-2 py-0.5 font-ui text-[12px] text-muted-ink"
                >
                  {TYPE_LABELS[t] ?? t}
                </span>
              ))}
            </div>
          )}

          <ChartCard title="每日做题量 / 正确率">
            {trend.length === 0 ? (
              <p className="py-8 text-center text-[13px] text-quiet">所选时间窗内暂无做题数据</p>
            ) : (
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
            )}
          </ChartCard>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <ChartCard title="最薄弱考点（掌握度 %）">
              {weak.length === 0 ? (
                <p className="py-8 text-center text-[13px] text-quiet">暂无掌握度数据</p>
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
                <p className="py-8 text-center text-[13px] text-quiet">暂无分题型数据</p>
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
