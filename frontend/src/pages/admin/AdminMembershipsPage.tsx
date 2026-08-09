import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  grantMembership,
  grantMembershipByUsername,
  listMemberships,
  revokeMembership,
} from '@/api/admin'
import { displayName } from '@/lib/adminDisplay'
import { queryClient } from '@/lib/queryClient'
import { toastApiError } from '@/lib/errors'
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

/** 校验是否为正整数天数。 */
function isValidDays(v: string): boolean {
  return /^\d+$/.test(v.trim()) && Number(v) > 0
}

/** 开通天数弹窗：输入天数（正整数，默认 30）。 */
function GrantDialog({
  label,
  onConfirm,
  pending,
}: {
  label: string
  onConfirm: (days: number) => void
  pending: boolean
}) {
  const [open, setOpen] = useState(false)
  const [days, setDays] = useState('30')
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        if (!next) setDays('30')
      }}
    >
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          开通
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>开通会员</DialogTitle>
          <DialogDescription>为用户 {label} 开通指定天数的会员。</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-2">
          <Label htmlFor="grant-days">天数</Label>
          <Input
            id="grant-days"
            type="number"
            min={1}
            value={days}
            onChange={(e) => setDays(e.target.value)}
            placeholder="30"
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
            disabled={!isValidDays(days) || pending}
            onClick={() => {
              onConfirm(Number(days))
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

export function AdminMembershipsPage() {
  const [q, setQ] = useState('')
  const memberships = useQuery({
    queryKey: ['admin', 'memberships', q],
    queryFn: () => listMemberships(q),
  })

  // 顶部直开表单：按用户名授予会员（可能尚无会员行）。
  const [grantUsername, setGrantUsername] = useState('')
  const [grantDays, setGrantDays] = useState('30')

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['admin'] })

  const grantMutation = useMutation({
    mutationFn: ({ id, days }: { id: string; days: number }) => grantMembership(id, { days }),
    onSuccess: () => {
      invalidate()
      toast.success('会员已开通')
    },
    onError: toastApiError,
  })

  const grantByUsernameMutation = useMutation({
    mutationFn: ({ username, days }: { username: string; days: number }) =>
      grantMembershipByUsername(username, days),
    onSuccess: () => {
      invalidate()
      toast.success('会员已开通')
      setGrantUsername('')
    },
    onError: toastApiError,
  })

  const revokeMutation = useMutation({
    mutationFn: (id: string) => revokeMembership(id),
    onSuccess: () => {
      invalidate()
      toast.success('会员已取消')
    },
    onError: toastApiError,
  })

  const topGrantValid = grantUsername.trim().length > 0 && isValidDays(grantDays)

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-[20px] text-ink [font-family:var(--font-display)]">会员</h1>

      <div className="flex flex-wrap items-end gap-2 rounded-md border border-hairline bg-wash/40 p-3">
        <div className="flex flex-col gap-1">
          <Label htmlFor="top-grant-username" className="text-quiet">
            用户名
          </Label>
          <Input
            id="top-grant-username"
            value={grantUsername}
            onChange={(e) => setGrantUsername(e.target.value)}
            placeholder="用户名"
            className="w-[220px]"
          />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="top-grant-days" className="text-quiet">
            天数
          </Label>
          <Input
            id="top-grant-days"
            type="number"
            min={1}
            value={grantDays}
            onChange={(e) => setGrantDays(e.target.value)}
            placeholder="30"
            className="w-[100px]"
          />
        </div>
        <Button
          size="sm"
          disabled={!topGrantValid || grantByUsernameMutation.isPending}
          onClick={() =>
            grantByUsernameMutation.mutate({
              username: grantUsername.trim(),
              days: Number(grantDays),
            })
          }
        >
          开通
        </Button>
      </div>

      <Input
        placeholder="搜索用户名…"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        className="max-w-[280px]"
      />

      <div className="overflow-hidden rounded-md border border-hairline">
        <table className="w-full text-[13px]">
          <thead className="bg-wash/60 text-left font-ui text-muted-ink">
            <tr>
              <th className="px-3 py-2">用户</th>
              <th className="px-3 py-2">到期时间</th>
              <th className="px-3 py-2">状态</th>
              <th className="px-3 py-2">操作</th>
            </tr>
          </thead>
          <tbody>
            {(memberships.data?.items ?? []).map((m) => (
              <tr key={m.user_id} className="border-t border-hairline hover:bg-tint/40">
                <td className="px-3 py-2 text-ink">
                  {displayName(m.username)}
                  <div className="text-[11px] text-quiet">{m.user_id}</div>
                </td>
                <td className="px-3 py-2 text-muted-ink">
                  {m.expires_at ? m.expires_at.slice(0, 10) : '—'}
                </td>
                <td className="px-3 py-2 text-muted-ink">{m.active ? '有效' : '已过期/无'}</td>
                <td className="px-3 py-2">
                  <div className="flex gap-2">
                    <GrantDialog
                      label={displayName(m.username)}
                      pending={grantMutation.isPending}
                      onConfirm={(days) => grantMutation.mutate({ id: m.user_id, days })}
                    />
                    <ConfirmDialog
                      trigger={
                        <Button variant="outline" size="sm">
                          取消
                        </Button>
                      }
                      title="取消会员"
                      description={`确认取消用户 ${displayName(m.username)} 的会员？`}
                      confirmLabel="确认"
                      pending={revokeMutation.isPending}
                      onConfirm={() => revokeMutation.mutate(m.user_id)}
                    />
                  </div>
                </td>
              </tr>
            ))}
            {memberships.isLoading && (
              <tr>
                <td colSpan={4} className="px-3 py-6 text-center text-quiet">
                  加载中…
                </td>
              </tr>
            )}
            {memberships.isError && (
              <tr>
                <td colSpan={4} className="px-3 py-6 text-center text-muted-ink">
                  会员记录加载失败{' '}
                  <button className="text-accent hover:underline" onClick={() => memberships.refetch()}>
                    重试
                  </button>
                </td>
              </tr>
            )}
            {!memberships.isLoading && !memberships.isError && memberships.data && memberships.data.items.length === 0 && (
              <tr>
                <td colSpan={4} className="px-3 py-6 text-center text-quiet">
                  暂无会员记录
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
