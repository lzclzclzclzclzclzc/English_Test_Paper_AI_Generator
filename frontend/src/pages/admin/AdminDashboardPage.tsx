import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import {
  getAnalytics,
  getOverview,
  getRevenue,
  getSystemHealth,
  getTimeseries,
  getUsageStats,
} from '@/api/admin'
import { useKnowledgePoints } from '@/hooks/useKnowledgePoints'
import { drillBySlug } from '@/lib/drillConfig'
import { prettifyKp, TYPE_LABELS } from '@/lib/kp'
import { formatYuan } from '@/lib/money'
import { cn } from '@/lib/utils'

const WEAK_THRESHOLD = 0.4

// 分科色轮（复用 colors.css 语义色），给柱状图多彩着色 → 呼应工作台 bento 色块。
const PALETTE = ['var(--accent)', 'var(--listening)', 'var(--reading)', 'var(--grammar)', 'var(--writing)', 'var(--success)']

const WINDOWS = [
  { label: '近 7 天', days: 7 },
  { label: '近 30 天', days: 30 },
  { label: '全部', days: 0 },
] as const

/** credit_ledger.action → 中文名。 */
const ACTION_LABELS: Record<string, string> = {
  generate_original: '出卷·真题原样',
  generate_light: '出卷·AI 改编',
  generate_fresh: '出卷·全新出题',
  revise_paper: '一句话重新出卷',
  solution: 'AI 单题讲解',
  writing_grade: '作文批改',
  vocab_example: '背单词·AI 例句',
  agent_message: '学习助手·消息',
}

/** paper.metadata.source → 中文名。drill:<slug> 走 drillConfig 取题型名。 */
const SOURCE_LABELS: Record<string, string> = {
  generate: '一句话出卷',
  dashboard: '主页快捷',
  daily: '每日一练',
  themes: '主题出卷',
  custom: '自选组卷',
  mock: '整卷模拟',
  mastery_review: '掌握度·复习',
  errorbook: '错题本',
  paper_retry: '试卷内错题重练',
  agent: '学习助手',
  study_plan: '学习计划',
  unknown: '未标记（历史）',
}

function sourceLabel(source: string): string {
  if (source.startsWith('drill:')) {
    const slug = source.slice('drill:'.length)
    return `专项·${drillBySlug(slug)?.label ?? slug}`
  }
  return SOURCE_LABELS[source] ?? source
}

const MODE_LABELS: Record<string, string> = {
  fresh: '普通出卷',
  remediation: '错题巩固',
  review: '复习薄弱',
  unknown: '未标记',
}

// ── 小组件 ────────────────────────────────────────────────────────────────

/** 模块分隔标题：显示体标题 + 细色规，分模块留白。 */
function ModuleTitle({ children, tint = 'var(--ink-30)' }: { children: React.ReactNode; tint?: string }) {
  return (
    <div className="mt-2 flex items-center gap-3">
      <span className="h-3.5 w-1 rounded-full" style={{ background: tint }} />
      <h2 className="shrink-0 text-[15px] font-semibold text-ink [font-family:var(--font-display)]">{children}</h2>
      <span className="h-px flex-1 bg-[var(--ink-10)]" />
    </div>
  )
}

/** 大数字统计卡：复用工作台 .card-stat 规格。 */
function StatCard({ variant, kicker, value, unit, span = 'col-2' }: {
  variant: string; kicker: string; value: string | number; unit?: string; span?: string
}) {
  return (
    <div className={cn('card', variant, span)}>
      <span className="card-kicker">{kicker}</span>
      <span className="card-stat mt-1">
        <span className="n">{value}</span>
        {unit && <span className="u">{unit}</span>}
      </span>
    </div>
  )
}

function CardEmpty() {
  return <p className="py-10 text-center text-[12.5px] text-quiet">暂无数据</p>
}

function CardLoading() {
  return <p className="py-10 text-center text-[12.5px] text-quiet">加载中…</p>
}

const AXIS_TICK = { fontSize: 11, fill: 'var(--text-quiet)' } as const
const LABEL_STYLE = { fontSize: 11, fontWeight: 600, fill: 'var(--text-muted)' } as const

/** 多彩横向柱（分科色轮）+ 数值标签。柱短小圆角，去坐标轴线，干净。 */
function HBar({ data, barKey = 'count', labelKey, unit, catWidth = 118, cells }: {
  data: Record<string, unknown>[]
  barKey?: string
  labelKey?: string
  unit?: string
  catWidth?: number
  cells?: (i: number, row: Record<string, unknown>) => string
}) {
  return (
    <ResponsiveContainer width="100%" height={Math.max(150, data.length * 40)}>
      <BarChart data={data} layout="vertical" margin={{ left: 4, right: 40, top: 4, bottom: 4 }}>
        <XAxis type="number" hide domain={unit === '%' ? [0, 100] : [0, 'dataMax']} />
        <YAxis type="category" dataKey="name" width={catWidth} interval={0} tickLine={false} axisLine={false} tick={AXIS_TICK} />
        <Tooltip cursor={{ fill: 'var(--ink-5)' }} />
        <Bar dataKey={barKey} radius={[0, 5, 5, 0]} maxBarSize={18} isAnimationActive={false}>
          {data.map((row, i) => (
            <Cell key={i} fill={cells ? cells(i, row) : PALETTE[i % PALETTE.length]} />
          ))}
          <LabelList dataKey={labelKey ?? barKey} position="right" style={LABEL_STYLE} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

/** 多彩竖向柱 + 顶部数值标签。 */
function VBar({ data, barKey = 'count', labelKey, height = 210 }: {
  data: Record<string, unknown>[]; barKey?: string; labelKey?: string; height?: number
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ left: 0, right: 8, top: 16, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--ink-10)" vertical={false} />
        <XAxis dataKey="name" tickLine={false} axisLine={false} tick={AXIS_TICK} />
        <YAxis allowDecimals={false} width={30} tickLine={false} axisLine={false} tick={AXIS_TICK} />
        <Tooltip cursor={{ fill: 'var(--ink-5)' }} />
        <Bar dataKey={barKey} radius={[5, 5, 0, 0]} maxBarSize={56} isAnimationActive={false}>
          {data.map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
          <LabelList dataKey={labelKey ?? barKey} position="top" style={LABEL_STYLE} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

/** 单色趋势折线（按模块色）。 */
function Trend({ data, color, height = 170 }: { data: { day: string; value: number }[]; color: string; height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ left: 0, right: 8, top: 6, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--ink-10)" />
        <XAxis dataKey="day" tickLine={false} axisLine={false} tick={AXIS_TICK} />
        <YAxis allowDecimals={false} width={28} tickLine={false} axisLine={false} tick={AXIS_TICK} />
        <Tooltip cursor={{ stroke: 'var(--ink-10)' }} />
        <Line type="monotone" dataKey="value" stroke={color} strokeWidth={2.5} dot={{ r: 2.5, fill: color, strokeWidth: 0 }} activeDot={{ r: 4 }} />
      </LineChart>
    </ResponsiveContainer>
  )
}

/** 系统健康折叠区块。 */
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

/**
 * 监控看板：一屏汇总运行监控数据，bento 色块分模块（呼应工作台/广告页视觉）。
 * 顶部天窗（近 7 / 30 天 / 全部）驱动窗口化区块；顶部指标卡为累计口径。
 * 大部分数据复用既有端点，仅「功能使用」走 /admin/stats/usage。
 */
export function AdminDashboardPage() {
  useKnowledgePoints()
  const [days, setDays] = useState(30)
  const span = days === 0 ? 3650 : days // timeseries / revenue 后端不识别 0=全部

  const overview = useQuery({ queryKey: ['admin', 'overview'], queryFn: getOverview })
  const usage = useQuery({ queryKey: ['admin', 'usage', days], queryFn: () => getUsageStats(days) })
  const series = useQuery({ queryKey: ['admin', 'timeseries', span], queryFn: () => getTimeseries(span) })
  const analytics = useQuery({ queryKey: ['admin', 'analytics', days], queryFn: () => getAnalytics(days) })
  const revenue = useQuery({ queryKey: ['admin', 'revenue', span], queryFn: () => getRevenue(span) })

  const anyError = [overview, usage, series, analytics, revenue].some((q) => q.isError)
  const refetchAll = () => { overview.refetch(); usage.refetch(); series.refetch(); analytics.refetch(); revenue.refetch() }

  const o = overview.data
  const u = usage.data

  const byAction = (u?.by_action ?? []).map((a) => ({ name: ACTION_LABELS[a.action] ?? a.action, count: a.count, credits: a.credits_spent }))
  const bySource = (u?.by_source ?? []).map((s) => ({ name: sourceLabel(s.source), count: s.count }))
  const byMode = (u?.by_mode ?? []).map((m) => ({ name: MODE_LABELS[m.mode] ?? m.mode, count: m.count }))
  const vocabTrend = (u?.vocabulary_by_day ?? []).map((v) => ({ day: v.day.slice(5), value: v.studied }))

  const usersTrend = (series.data?.users_by_day ?? []).map((d) => ({ day: d.day.slice(5), value: d.count }))
  const papersTrend = (series.data?.papers_by_day ?? []).map((d) => ({ day: d.day.slice(5), value: d.count }))

  const attemptsTrend = (analytics.data?.attempts_by_day ?? []).map((d) => ({
    day: d.day.slice(5),
    attempts: d.attempts,
    rate: d.correct_rate == null ? null : Math.round(d.correct_rate * 100),
  }))
  const weak = (analytics.data?.site_mastery?.weak_kps ?? []).map((k) => ({
    name: prettifyKp(k.knowledge_point_id),
    mastery: Math.round(k.mastery * 100),
    masteryLabel: `${Math.round(k.mastery * 100)}%`,
    weak: k.mastery < WEAK_THRESHOLD,
  }))
  const types = (analytics.data?.type_accuracy ?? []).map((t) => ({
    name: TYPE_LABELS[t.question_type] ?? t.question_type,
    accuracy: Math.round(t.accuracy * 100),
    accuracyLabel: `${Math.round(t.accuracy * 100)}%`,
  }))

  const revByDay = (revenue.data?.revenue_by_day ?? []).map((d) => ({ day: d.day.slice(5), cents: d.cents, yuan: formatYuan(d.cents) }))
  const byPack = revenue.data?.by_pack ?? []
  // 按套餐：套餐为横坐标，订单数（左轴）与金额（右轴，元）为纵坐标 → 双轴分组柱。
  const packData = byPack.map((p) => ({ name: p.pack_id, orders: p.orders, yuan: p.cents / 100, yuanLabel: formatYuan(p.cents) }))

  return (
    <div className="flex max-w-[64rem] flex-col gap-7">
      <div className="flex items-center justify-between">
        <h1 className="text-[22px] text-ink [font-family:var(--font-display)]">监控看板</h1>
        <div className="flex gap-1">
          {WINDOWS.map((w) => (
            <button
              key={w.days}
              onClick={() => setDays(w.days)}
              className={cn(
                'h-8 rounded-lg border px-3 font-ui text-[13px] transition-colors',
                days === w.days ? 'border-accent bg-wash text-accent' : 'border-hairline text-muted-ink hover:bg-tint/40',
              )}
            >
              {w.label}
            </button>
          ))}
        </div>
      </div>

      {anyError && (
        <div className="flex items-center gap-3 rounded-md border border-hairline bg-wash/40 px-4 py-3">
          <p className="text-[13px] text-muted-ink">部分数据加载失败</p>
          <button className="text-[13px] text-accent hover:underline" onClick={refetchAll}>重试</button>
        </div>
      )}

      {/* ── 累计概览（全时口径，大数字色块） ── */}
      <ModuleTitle tint="var(--accent)">累计概览</ModuleTitle>
      <div className="bento">
        <StatCard variant="is-accent" kicker="总用户" value={o?.total_users ?? '—'} />
        <StatCard variant="is-grammar" kicker="今日新增" value={o?.new_users_today ?? '—'} />
        <StatCard variant="is-success" kicker="付费用户" value={o?.paying_users ?? '—'} />
        <StatCard variant="is-listening" kicker="试卷总数" value={o?.total_papers ?? '—'} />
        <StatCard variant="is-reading" kicker="总做题数" value={o?.total_attempts ?? '—'} />
        <StatCard variant="is-writing" kicker="累计收入" value={o?.total_revenue_cents == null ? '—' : formatYuan(o.total_revenue_cents)} />
      </div>

      {/* ── 功能使用 ── */}
      <ModuleTitle tint="var(--accent)">功能使用</ModuleTitle>
      <div className="bento">
        <div className="card is-accent col-6">
          <span className="card-kicker">各 AI 功能调用量（次）</span>
          {usage.isLoading ? <CardLoading /> : byAction.length === 0 ? <CardEmpty /> : (
            <HBar data={byAction} catWidth={130} />
          )}
        </div>
        <div className="card is-listening col-3">
          <span className="card-kicker">出卷来源分布 · 页面偏好</span>
          {usage.isLoading ? <CardLoading /> : bySource.length === 0 ? <CardEmpty /> : (
            <HBar data={bySource} catWidth={122} />
          )}
        </div>
        <div className="card is-reading col-3">
          <span className="card-kicker">出卷类型分布</span>
          {usage.isLoading ? <CardLoading /> : byMode.length === 0 ? <CardEmpty /> : (
            <VBar data={byMode} />
          )}
        </div>
      </div>

      {/* ── 参与度趋势 ── */}
      <ModuleTitle tint="var(--listening)">参与度趋势</ModuleTitle>
      <div className="bento">
        <div className="card is-accent col-6">
          <span className="card-kicker">每日新增用户</span>
          {usersTrend.length === 0 ? <CardEmpty /> : <Trend data={usersTrend} color="var(--accent)" />}
        </div>
        <div className="card is-listening col-6">
          <span className="card-kicker">每日生成试卷</span>
          {papersTrend.length === 0 ? <CardEmpty /> : <Trend data={papersTrend} color="var(--listening)" />}
        </div>
        <div className="card is-reading col-6">
          <span className="card-kicker">每日背单词量</span>
          {usage.isLoading ? <CardLoading /> : vocabTrend.length === 0 ? <CardEmpty /> : <Trend data={vocabTrend} color="var(--reading)" />}
        </div>
      </div>

      {/* ── 学习质量 ── */}
      <ModuleTitle tint="var(--reading)">学习质量</ModuleTitle>
      <div className="bento">
        <div className="card is-reading col-6">
          <span className="card-kicker">每日做题量 / 正确率</span>
          {attemptsTrend.length === 0 ? <CardEmpty /> : (
            <ResponsiveContainer width="100%" height={230}>
              <LineChart data={attemptsTrend} margin={{ left: 0, right: 8, top: 6, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--ink-10)" />
                <XAxis dataKey="day" tickLine={false} axisLine={false} tick={AXIS_TICK} />
                <YAxis yAxisId="vol" allowDecimals={false} width={30} tickLine={false} axisLine={false} tick={AXIS_TICK} />
                <YAxis yAxisId="rate" orientation="right" domain={[0, 100]} width={38} unit="%" tickLine={false} axisLine={false} tick={AXIS_TICK} />
                <Tooltip cursor={{ stroke: 'var(--ink-10)' }} />
                <Line yAxisId="vol" type="monotone" dataKey="attempts" name="做题量" stroke="var(--reading)" strokeWidth={2.5} dot={{ r: 2.5, fill: 'var(--reading)', strokeWidth: 0 }} activeDot={{ r: 4 }} />
                <Line yAxisId="rate" type="monotone" dataKey="rate" name="正确率(%)" stroke="var(--accent)" strokeWidth={2} strokeDasharray="4 3" dot={false} connectNulls />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
        <div className="card is-grammar col-3">
          <span className="card-kicker">分题型准确率</span>
          {types.length === 0 ? <CardEmpty /> : <HBar data={types} barKey="accuracy" labelKey="accuracyLabel" unit="%" catWidth={112} />}
        </div>
        <div className="card is-writing col-3">
          <span className="card-kicker">最薄弱考点 · 掌握度</span>
          {weak.length === 0 ? <CardEmpty /> : (
            <HBar
              data={weak}
              barKey="mastery"
              labelKey="masteryLabel"
              unit="%"
              catWidth={132}
              cells={(_, row) => ((row as { weak?: boolean }).weak ? 'var(--accent)' : 'var(--ink-30)')}
            />
          )}
        </div>
      </div>

      {/* ── 作文 ── */}
      <ModuleTitle tint="var(--writing)">作文批改</ModuleTitle>
      <div className="bento">
        <StatCard variant="is-writing" span="col-3" kicker="作文批改篇数" value={u?.writing.count ?? '—'} unit={`近 ${days === 0 ? '全部' : days + ' 天'}`} />
        <StatCard variant="is-writing" span="col-3" kicker="作文平均分" value={u?.writing.avg_score ?? '—'} unit="批改口径" />
      </div>

      {/* ── 营收 ── */}
      <ModuleTitle tint="var(--success)">营收</ModuleTitle>
      <div className="bento">
        <div className="card is-success col-3">
          <span className="card-kicker">每日收入</span>
          {revByDay.length === 0 ? <CardEmpty /> : (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={revByDay} margin={{ left: 8, right: 8, top: 16, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--ink-10)" vertical={false} />
                <XAxis dataKey="day" tickLine={false} axisLine={false} tick={AXIS_TICK} />
                <YAxis width={48} tickLine={false} axisLine={false} tick={AXIS_TICK} tickFormatter={(v: number) => formatYuan(v)} />
                <Tooltip cursor={{ fill: 'var(--ink-5)' }} formatter={(v) => [formatYuan(Number(v)), '收入']} />
                <Bar dataKey="cents" fill="var(--success)" radius={[5, 5, 0, 0]} maxBarSize={38} isAnimationActive={false}>
                  <LabelList dataKey="yuan" position="top" style={LABEL_STYLE} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
        <div className="card is-listening col-3">
          <span className="card-kicker">按套餐收入 · 订单数与金额</span>
          {packData.length === 0 ? <CardEmpty /> : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={packData} margin={{ left: 0, right: 8, top: 16, bottom: 4 }} barGap={6}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--ink-10)" vertical={false} />
                <XAxis dataKey="name" tickLine={false} axisLine={false} tick={AXIS_TICK} />
                <YAxis yAxisId="orders" allowDecimals={false} width={30} tickLine={false} axisLine={false} tick={AXIS_TICK} />
                <YAxis yAxisId="amt" orientation="right" width={48} tickLine={false} axisLine={false} tick={AXIS_TICK} tickFormatter={(v: number) => formatYuan(v * 100)} />
                <Tooltip cursor={{ fill: 'var(--ink-5)' }} formatter={(v, n) => (n === '金额(元)' ? [formatYuan(Number(v) * 100), n] : [v, n])} />
                <Bar yAxisId="orders" dataKey="orders" name="订单数" fill="var(--listening)" radius={[5, 5, 0, 0]} maxBarSize={40} isAnimationActive={false}>
                  <LabelList dataKey="orders" position="top" style={LABEL_STYLE} />
                </Bar>
                <Bar yAxisId="amt" dataKey="yuan" name="金额(元)" fill="var(--success)" radius={[5, 5, 0, 0]} maxBarSize={40} isAnimationActive={false}>
                  <LabelList dataKey="yuanLabel" position="top" style={LABEL_STYLE} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      <SystemHealthPanel />
    </div>
  )
}
