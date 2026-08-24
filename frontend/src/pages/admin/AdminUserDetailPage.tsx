import { useMemo, useState, type ReactNode } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { toast } from 'sonner'
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
import {
  banUser,
  getUserAnalytics,
  getUserAttempts,
  getUserDetail,
  getUserMastery,
  getUserPapers,
  resetPassword,
  setRole,
  unbanUser,
} from '@/api/admin'
import { useKnowledgePoints } from '@/hooks/useKnowledgePoints'
import { prettifyKp, TYPE_LABELS } from '@/lib/kp'
import { masteryToOutline } from '@/lib/masteryOutline'
import { cn } from '@/lib/utils'
import { queryClient } from '@/lib/queryClient'
import { toastApiError } from '@/lib/errors'
import { MindmapView } from '@/components/mindmap/MindmapView'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { ConfirmDialog } from '@/components/admin/ConfirmDialog'

const ACCENT = '#ef4a2b'
const WEAK_THRESHOLD = 0.4

const WINDOWS = [
  { label: '近 7 天', days: 7 },
  { label: '近 30 天', days: 30 },
  { label: '全部', days: 0 },
] as const

function Field({ label, value, hint }: { label: string; value: ReactNode; hint?: ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <div className="text-[12px] text-quiet">{label}</div>
      <div className="font-ui text-[15px] text-ink">{value}</div>
      {hint != null && <div className="text-[11px] text-quiet">{hint}</div>}
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border border-hairline bg-wash/40 px-4 py-3">
      <div className="text-[12px] text-quiet">{label}</div>
      <div className="mt-1 font-ui text-[22px] font-bold tabular-nums text-ink">{value}</div>
    </div>
  )
}

function ChartCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-md border border-hairline p-4">
      <div className="mb-2 text-[13px] text-muted-ink">{title}</div>
      {children}
    </div>
  )
}

/** 简单列表区块标题（最近试卷 / 最近做题共用样式）。 */
function SectionTitle({ children }: { children: ReactNode }) {
  return (
    <h2 className="text-[16px] text-ink [font-family:var(--font-display)]">{children}</h2>
  )
}

/** 列表加载/出错态的统一展示。 */
function SectionState({ isLoading, isError, onRetry }: { isLoading: boolean; isError: boolean; onRetry: () => void }) {
  if (isLoading) return <p className="text-[13px] text-quiet">加载中…</p>
  if (isError)
    return (
      <p className="text-[13px] text-muted-ink">
        加载失败{' '}
        <button className="text-accent hover:underline" onClick={onRetry}>
          重试
        </button>
      </p>
    )
  return null
}

/** 重置密码弹窗：输入新密码（≥6 位）。 */
function ResetPasswordDialog({
  onConfirm,
  pending,
}: {
  onConfirm: (pw: string) => void
  pending: boolean
}) {
  const [open, setOpen] = useState(false)
  const [pw, setPw] = useState('')
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        if (!next) setPw('')
      }}
    >
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          重置密码
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>重置密码</DialogTitle>
          <DialogDescription>设置一个新密码，该用户需重新登录。</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-2">
          <Label htmlFor="new-password">新密码</Label>
          <Input
            id="new-password"
            type="password"
            value={pw}
            onChange={(e) => setPw(e.target.value)}
            placeholder="至少 6 位"
          />
        </div>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline" size="sm">
              取消
            </Button>
          </DialogClose>
          <Button
            size="sm"
            disabled={pw.length < 6 || pending}
            onClick={() => {
              onConfirm(pw)
              setOpen(false)
            }}
          >
            确认
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/**
 * 用户详情页（Spec H B）：身份 / 管理操作 + 学情数据可视化（原「学情」页并入）
 * + 背单词每日词量。学习画像的数据以图表呈现（每日做题、薄弱考点、分题型准确率），
 * 不再另放一份文字版掌握度报告（去重）。
 */
export function AdminUserDetailPage() {
  useKnowledgePoints() // 确保考点中文名可用
  const { userId } = useParams<{ userId: string }>()
  const [days, setDays] = useState(30)

  const detail = useQuery({
    queryKey: ['admin', 'user', userId],
    queryFn: () => getUserDetail(userId!),
    enabled: !!userId,
  })

  const mastery = useQuery({
    queryKey: ['admin', 'user', userId, 'mastery'],
    queryFn: () => getUserMastery(userId!),
    enabled: !!userId,
  })

  const analytics = useQuery({
    queryKey: ['admin', 'user', userId, 'analytics', days],
    queryFn: () => getUserAnalytics(userId!, days),
    enabled: !!userId,
  })

  const papers = useQuery({
    queryKey: ['admin', 'user', userId, 'papers'],
    queryFn: () => getUserPapers(userId!),
    enabled: !!userId,
  })

  const attempts = useQuery({
    queryKey: ['admin', 'user', userId, 'attempts'],
    queryFn: () => getUserAttempts(userId!),
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
  const vocab = useMemo(
    () =>
      (analytics.data?.vocabulary_by_day ?? []).map((d) => ({
        day: d.day.slice(5), // MM-DD
        new_words: d.new_words,
        review_words: d.review_words,
        studied: d.studied,
      })),
    [analytics.data],
  )
  const vocabTotal = useMemo(() => vocab.reduce((sum, d) => sum + d.studied, 0), [vocab])

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['admin'] })

  const roleMutation = useMutation({
    mutationFn: (role: 'user' | 'admin') => setRole(userId!, role),
    onSuccess: () => {
      invalidate()
      toast.success('角色已更新')
    },
    onError: toastApiError,
  })

  const banMutation = useMutation({
    mutationFn: (action: 'ban' | 'unban') =>
      action === 'ban' ? banUser(userId!) : unbanUser(userId!),
    onSuccess: (_data, action) => {
      invalidate()
      toast.success(action === 'ban' ? '用户已封禁' : '用户已解封')
    },
    onError: toastApiError,
  })

  const passwordMutation = useMutation({
    mutationFn: (pw: string) => resetPassword(userId!, pw),
    onSuccess: () => {
      invalidate()
      toast.success('密码已重置，该用户需重新登录')
    },
    onError: toastApiError,
  })

  if (detail.isLoading) return <div className="text-muted-ink">加载中…</div>
  if (detail.isError)
    return (
      <div className="text-muted-ink">
        加载失败{' '}
        <button className="text-accent hover:underline" onClick={() => detail.refetch()}>
          重试
        </button>
      </div>
    )

  const u = detail.data
  if (!u) return <div className="text-muted-ink">未找到用户</div>

  const isAdmin = u.role === 'admin'
  const isBanned = u.status === 'banned'

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-[20px] text-ink [font-family:var(--font-display)]">{u.username}</h1>
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
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Field label="注册时间" value={u.created_at.slice(0, 10)} />
        <Field label="角色" value={isAdmin ? '管理员' : '用户'} />
        <Field
          label="状态"
          value={<span className={isBanned ? 'text-accent' : 'text-ink'}>{isBanned ? '已封禁' : '正常'}</span>}
        />
        <Field
          label="积分余额"
          value={u.credits_balance + u.credits_daily_balance}
          hint={`永久 ${u.credits_balance} · 今日赠送 ${u.credits_daily_balance}`}
        />
      </div>

      <div className="flex gap-2">
        <ConfirmDialog
          trigger={
            <Button variant="outline" size="sm">
              {isAdmin ? '取消管理员' : '设为管理员'}
            </Button>
          }
          title={isAdmin ? '取消管理员' : '设为管理员'}
          description={
            isAdmin
              ? `确认将 ${u.username} 降级为普通用户？`
              : `确认将 ${u.username} 提升为管理员？`
          }
          confirmLabel="确认"
          pending={roleMutation.isPending}
          onConfirm={() => roleMutation.mutate(isAdmin ? 'user' : 'admin')}
        />

        <ConfirmDialog
          trigger={
            <Button variant="outline" size="sm">
              {isBanned ? '解封' : '封禁'}
            </Button>
          }
          title={isBanned ? '解封用户' : '封禁用户'}
          description={
            isBanned
              ? `确认解封 ${u.username}？`
              : `确认封禁 ${u.username}？封禁后该用户将无法登录。`
          }
          confirmLabel="确认"
          pending={banMutation.isPending}
          onConfirm={() => banMutation.mutate(isBanned ? 'unban' : 'ban')}
        />

        <ResetPasswordDialog
          pending={passwordMutation.isPending}
          onConfirm={(pw) => passwordMutation.mutate(pw)}
        />
      </div>

      {/* 学情概览指标（原「学情」页并入） */}
      <div className="grid grid-cols-2 gap-3 border-t border-hairline pt-6 sm:grid-cols-4">
        <Metric label="试卷数" value={u.paper_count} />
        <Metric label="做题数" value={u.attempt_count} />
        <Metric label="总正确率" value={u.correct_rate == null ? '—' : `${Math.round(u.correct_rate * 100)}%`} />
        <Metric label="纳入统计作答" value={mastery.data?.total_attempts_considered ?? '—'} />
        {mastery.data && mastery.data.writing_graded_count > 0 && mastery.data.writing_avg_score != null && (
          <Metric
            label="写作平均分"
            value={`${mastery.data.writing_avg_score} / ${mastery.data.writing_full_score}（${mastery.data.writing_graded_count} 篇）`}
          />
        )}
      </div>

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

      {(analytics.isLoading || mastery.isLoading) && (
        <p className="text-[13px] text-quiet">学情数据加载中…</p>
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

      {/* 掌握情况脑图（与学生端学情报告同款，纯前端从掌握度生成） */}
      {mastery.data && mastery.data.weak_kps.length > 0 && (
        <ChartCard title="掌握情况脑图">
          <p className="mb-2 text-[12px] text-quiet">
            按掌握程度分为薄弱 / 一般 / 扎实三支，括号内为正确率。
          </p>
          <div className="h-[300px] w-full overflow-hidden rounded-sm border border-hairline bg-card-surface">
            <MindmapView outline={masteryToOutline(mastery.data)} />
          </div>
        </ChartCard>
      )}

      {/* 背单词：每日背词量（新学 / 复习堆叠） */}
      <ChartCard title={`背单词 · 每日词量${vocabTotal > 0 ? `（窗口内共 ${vocabTotal} 词）` : ''}`}>
        {vocab.length === 0 ? (
          <p className="py-8 text-center text-[13px] text-quiet">所选时间窗内暂无背词记录</p>
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={vocab}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--ink-10)" />
              <XAxis dataKey="day" tick={{ fontSize: 11 }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 11 }} width={32} />
              <Tooltip />
              <Bar dataKey="new_words" name="新学" stackId="v" fill={ACCENT} />
              <Bar dataKey="review_words" name="复习" stackId="v" fill={ACCENT} fillOpacity={0.4} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </ChartCard>

      {/* 最近试卷（Spec H B） */}
      <div className="flex flex-col gap-3 border-t border-hairline pt-6">
        <SectionTitle>最近试卷</SectionTitle>
        <SectionState
          isLoading={papers.isLoading}
          isError={papers.isError}
          onRetry={() => papers.refetch()}
        />
        {papers.data && papers.data.items.length === 0 && (
          <p className="text-[13px] text-muted-ink">暂无试卷</p>
        )}
        {papers.data && papers.data.items.length > 0 && (
          <table className="w-full text-left text-[13px]">
            <thead>
              <tr className="border-b border-hairline text-quiet">
                <th className="py-1.5 pr-4 font-normal">试卷</th>
                <th className="py-1.5 pr-4 font-normal">生成时间</th>
                <th className="py-1.5 font-normal">题数</th>
              </tr>
            </thead>
            <tbody>
              {papers.data.items.map((p) => (
                <tr key={p.id} className="border-b border-hairline last:border-b-0">
                  <td className="py-1.5 pr-4 text-ink">{p.title}</td>
                  <td className="py-1.5 pr-4 text-quiet">{p.generated_at.slice(0, 16).replace('T', ' ')}</td>
                  <td className="py-1.5 text-quiet">{p.question_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* 最近做题记录（Spec H B） */}
      <div className="flex flex-col gap-3 border-t border-hairline pt-6">
        <SectionTitle>最近做题记录</SectionTitle>
        <SectionState
          isLoading={attempts.isLoading}
          isError={attempts.isError}
          onRetry={() => attempts.refetch()}
        />
        {attempts.data && attempts.data.items.length === 0 && (
          <p className="text-[13px] text-muted-ink">暂无做题记录</p>
        )}
        {attempts.data && attempts.data.items.length > 0 && (
          <table className="w-full text-left text-[13px]">
            <thead>
              <tr className="border-b border-hairline text-quiet">
                <th className="py-1.5 pr-4 font-normal">试卷</th>
                <th className="py-1.5 pr-4 font-normal">答题时间</th>
                <th className="py-1.5 pr-4 font-normal">对/总</th>
                <th className="py-1.5 font-normal">正确率</th>
              </tr>
            </thead>
            <tbody>
              {attempts.data.items.map((a) => (
                <tr key={a.attempt_id} className="border-b border-hairline last:border-b-0">
                  <td className="py-1.5 pr-4 text-ink">{a.paper_title}</td>
                  <td className="py-1.5 pr-4 text-quiet">{a.answered_at.slice(0, 16).replace('T', ' ')}</td>
                  <td className="py-1.5 pr-4 text-quiet">
                    {a.item_correct}/{a.item_total}
                  </td>
                  <td className="py-1.5 text-quiet">
                    {a.correct_rate == null ? '—' : `${Math.round(a.correct_rate * 100)}%`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
