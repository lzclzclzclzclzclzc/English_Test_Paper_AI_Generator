import { useState, type ReactNode } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { toast } from 'sonner'
import {
  banUser,
  getUserAttempts,
  getUserDetail,
  getUserMastery,
  getUserPapers,
  resetPassword,
  setRole,
  unbanUser,
} from '@/api/admin'
import { queryClient } from '@/lib/queryClient'
import { toastApiError } from '@/lib/errors'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { MasteryReport } from '@/components/MasteryReport'
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

function Field({ label, value }: { label: string; value: ReactNode }) {
  return (
    <>
      <div className="text-quiet">{label}</div>
      <div className="text-ink">{value}</div>
    </>
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

export function AdminUserDetailPage() {
  const { userId } = useParams<{ userId: string }>()
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
      <h1 className="text-[20px] text-ink [font-family:var(--font-display)]">{u.username}</h1>

      <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-[14px]">
        <Field label="注册时间" value={u.created_at.slice(0, 10)} />
        <Field label="角色" value={isAdmin ? '管理员' : '用户'} />
        <Field label="状态" value={isBanned ? '已封禁' : '正常'} />
        <Field label="试卷数" value={u.paper_count} />
        <Field label="做题数" value={u.attempt_count} />
        <Field
          label="正确率"
          value={u.correct_rate == null ? '暂无' : `${Math.round(u.correct_rate * 100)}%`}
        />
        <Field label="积分余额" value={`${u.credits_balance}（今日赠送剩余 ${u.credits_daily_balance}）`} />
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

      {/* 学习画像：复用学生端掌握度报告组件 */}
      <div className="flex flex-col gap-4 border-t border-hairline pt-6">
        <h2 className="text-[16px] text-ink [font-family:var(--font-display)]">学习画像</h2>
        {mastery.isLoading ? (
          <p className="text-[13px] text-quiet">加载中…</p>
        ) : mastery.isError ? (
          <p className="text-[13px] text-muted-ink">
            画像加载失败{' '}
            <button className="text-accent hover:underline" onClick={() => mastery.refetch()}>
              重试
            </button>
          </p>
        ) : mastery.data ? (
          <MasteryReport profile={mastery.data} hideActionCta />
        ) : null}
      </div>
    </div>
  )
}
