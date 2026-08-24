import { useState } from 'react'
import { keepPreviousData, useMutation, useQuery } from '@tanstack/react-query'
import { toast } from 'sonner'
import { adjustCredits, adjustCreditsByUsername, getCreditAccount, listCreditAccounts } from '@/api/admin'
import { Pagination } from '@/components/admin/Pagination'
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

const PAGE_SIZE = 50

const KIND_LABEL: Record<string, string> = {
  signup_bonus: '注册赠送',
  daily_grant: '每日赠送',
  purchase: '充值',
  spend: '消费',
  refund: '退回',
  admin_adjust: '管理员调整',
  migrate_membership: '会员折算',
}

/** 整数且非 0 才能提交（正加负减）。 */
function parseDelta(v: string): number | null {
  if (!/^-?\d+$/.test(v.trim())) return null
  const n = Number(v)
  return n === 0 ? null : n
}

/** 调整积分弹窗：delta（正加负减）+ 备注（必填，写进审计）。 */
function AdjustDialog({
  label,
  onConfirm,
  pending,
}: {
  label: string
  onConfirm: (delta: number, note: string) => void
  pending: boolean
}) {
  const [open, setOpen] = useState(false)
  const [delta, setDelta] = useState('100')
  const [note, setNote] = useState('')
  const parsed = parseDelta(delta)
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        if (!next) {
          setDelta('100')
          setNote('')
        }
      }}
    >
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          调整
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>调整积分</DialogTitle>
          <DialogDescription>为用户 {label} 增减积分（正数加、负数减，不会减到 0 以下）。备注会写入审计日志。</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <Label htmlFor="adjust-delta">积分变动</Label>
            <Input id="adjust-delta" type="number" value={delta} onChange={(e) => setDelta(e.target.value)} placeholder="100 或 -100" />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="adjust-note">备注</Label>
            <Input id="adjust-note" value={note} onChange={(e) => setNote(e.target.value)} placeholder="如：活动赠送 / 误扣补偿" maxLength={200} />
          </div>
        </div>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline" size="sm">
              取消
            </Button>
          </DialogClose>
          <Button
            size="sm"
            disabled={parsed === null || note.trim() === '' || pending}
            onClick={() => {
              if (parsed === null) return
              onConfirm(parsed, note.trim())
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

/** 流水弹窗：只读最近 50 条。 */
function LedgerDialog({ userId, label }: { userId: string; label: string }) {
  const [open, setOpen] = useState(false)
  const detail = useQuery({
    queryKey: ['admin', 'credits', userId],
    queryFn: () => getCreditAccount(userId, 50, 0),
    enabled: open,
  })
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          流水
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-[640px]">
        <DialogHeader>
          <DialogTitle>积分流水 · {label}</DialogTitle>
          <DialogDescription>
            {detail.data
              ? `余额 ${detail.data.balance} · 今日赠送剩余 ${detail.data.daily_balance} / ${detail.data.daily_grant} · 累计消费 ${detail.data.spent_total} · 共 ${detail.data.ledger_total} 条`
              : '加载中…'}
          </DialogDescription>
        </DialogHeader>
        <div className="max-h-[60vh] overflow-y-auto">
          <table className="w-full text-[12.5px]">
            <thead className="text-left font-ui text-quiet">
              <tr>
                <th className="py-1 pr-3">时间</th>
                <th className="py-1 pr-3">类型</th>
                <th className="py-1 pr-3 text-right">变动</th>
                <th className="py-1 pr-3 text-right">结余</th>
                <th className="py-1">备注</th>
              </tr>
            </thead>
            <tbody>
              {(detail.data?.ledger ?? []).map((r) => (
                <tr key={r.id} className="border-t border-hairline">
                  <td className="py-1 pr-3 font-ui tabular-nums text-quiet">{r.created_at.slice(5, 16).replace('T', ' ')}</td>
                  <td className="py-1 pr-3 text-ink">
                    {KIND_LABEL[r.kind] ?? r.kind}
                    <span className="text-quiet">{r.bucket === 'daily' ? ' · 今日' : ''}</span>
                  </td>
                  <td className="py-1 pr-3 text-right font-ui tabular-nums text-ink">{r.delta > 0 ? `+${r.delta}` : r.delta}</td>
                  <td className="py-1 pr-3 text-right font-ui tabular-nums text-quiet">{r.balance_after}</td>
                  <td className="py-1 text-quiet">{r.note ?? r.action ?? ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </DialogContent>
    </Dialog>
  )
}

export function AdminCreditsPage() {
  const [q, setQ] = useState('')
  const [page, setPage] = useState(1)
  const accounts = useQuery({
    queryKey: ['admin', 'credits', 'list', q, page],
    queryFn: () => listCreditAccounts(q, PAGE_SIZE, (page - 1) * PAGE_SIZE),
    placeholderData: keepPreviousData,
  })
  const total = accounts.data?.total ?? 0

  // 顶部直开表单：按用户名调整
  const [topUsername, setTopUsername] = useState('')
  const [topDelta, setTopDelta] = useState('100')
  const [topNote, setTopNote] = useState('')
  const topParsed = parseDelta(topDelta)

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['admin'] })

  const adjustMutation = useMutation({
    mutationFn: ({ id, delta, note }: { id: string; delta: number; note: string }) => adjustCredits(id, delta, note),
    onSuccess: (acct) => {
      invalidate()
      toast.success(`已调整，当前余额 ${acct.balance}`)
    },
    onError: toastApiError,
  })

  const adjustByUsernameMutation = useMutation({
    mutationFn: ({ username, delta, note }: { username: string; delta: number; note: string }) =>
      adjustCreditsByUsername(username, delta, note),
    onSuccess: (acct) => {
      invalidate()
      toast.success(`已调整 ${displayName(acct.username)}，当前余额 ${acct.balance}`)
      setTopUsername('')
      setTopNote('')
    },
    onError: toastApiError,
  })

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-[20px] text-ink [font-family:var(--font-display)]">积分</h1>

      <div className="flex flex-wrap items-end gap-2 rounded-md border border-hairline bg-wash/40 p-3">
        <div className="flex flex-col gap-1">
          <Label htmlFor="top-adjust-username" className="text-quiet">
            用户名
          </Label>
          <Input id="top-adjust-username" value={topUsername} onChange={(e) => setTopUsername(e.target.value)} placeholder="用户名" className="w-[200px]" />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="top-adjust-delta" className="text-quiet">
            变动（正加负减）
          </Label>
          <Input id="top-adjust-delta" type="number" value={topDelta} onChange={(e) => setTopDelta(e.target.value)} className="w-[120px]" />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="top-adjust-note" className="text-quiet">
            备注
          </Label>
          <Input id="top-adjust-note" value={topNote} onChange={(e) => setTopNote(e.target.value)} placeholder="写入审计" className="w-[220px]" maxLength={200} />
        </div>
        <Button
          size="sm"
          disabled={topUsername.trim() === '' || topParsed === null || topNote.trim() === '' || adjustByUsernameMutation.isPending}
          onClick={() => {
            if (topParsed === null) return
            adjustByUsernameMutation.mutate({ username: topUsername.trim(), delta: topParsed, note: topNote.trim() })
          }}
        >
          调整
        </Button>
      </div>

      <Input
        placeholder="搜索用户名…"
        value={q}
        onChange={(e) => {
          setQ(e.target.value)
          setPage(1)
        }}
        className="max-w-[280px]"
      />

      <div className="overflow-hidden rounded-md border border-hairline">
        <table className="w-full text-[13px]">
          <thead className="bg-wash/60 text-left font-ui text-muted-ink">
            <tr>
              <th className="px-3 py-2">用户</th>
              <th className="px-3 py-2 text-right">余额</th>
              <th className="px-3 py-2 text-right">今日赠送剩余</th>
              <th className="px-3 py-2">最近变动</th>
              <th className="px-3 py-2">操作</th>
            </tr>
          </thead>
          <tbody>
            {(accounts.data?.items ?? []).map((a) => (
              <tr key={a.user_id} className="border-t border-hairline hover:bg-tint/40">
                <td className="px-3 py-2 text-ink">
                  {displayName(a.username)}
                  <div className="text-[11px] text-quiet">{a.user_id}</div>
                </td>
                <td className="px-3 py-2 text-right font-ui tabular-nums text-ink">{a.balance}</td>
                <td className="px-3 py-2 text-right font-ui tabular-nums text-muted-ink">{a.daily_balance}</td>
                <td className="px-3 py-2 font-ui tabular-nums text-quiet">{a.updated_at ? a.updated_at.slice(0, 16).replace('T', ' ') : '—'}</td>
                <td className="px-3 py-2">
                  <div className="flex gap-2">
                    <AdjustDialog
                      label={displayName(a.username)}
                      pending={adjustMutation.isPending}
                      onConfirm={(delta, note) => adjustMutation.mutate({ id: a.user_id, delta, note })}
                    />
                    <LedgerDialog userId={a.user_id} label={displayName(a.username)} />
                  </div>
                </td>
              </tr>
            ))}
            {accounts.isLoading && (
              <tr>
                <td colSpan={5} className="px-3 py-6 text-center text-quiet">
                  加载中…
                </td>
              </tr>
            )}
            {accounts.isError && (
              <tr>
                <td colSpan={5} className="px-3 py-6 text-center text-muted-ink">
                  积分账户加载失败{' '}
                  <button className="text-accent hover:underline" onClick={() => accounts.refetch()}>
                    重试
                  </button>
                </td>
              </tr>
            )}
            {!accounts.isLoading && !accounts.isError && accounts.data && accounts.data.items.length === 0 && (
              <tr>
                <td colSpan={5} className="px-3 py-6 text-center text-quiet">
                  暂无数据
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <Pagination page={page} pageSize={PAGE_SIZE} total={total} onChange={setPage} />
    </div>
  )
}
