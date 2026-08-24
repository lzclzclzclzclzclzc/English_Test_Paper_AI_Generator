import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { PATHS } from '@/lib/paths'
import type { InsufficientCreditsDetail } from '@/types/payment'

/** 余额不足时弹出的信息：有 required/available 时显示具体数字；只有文案时显示文案。 */
export interface CreditsPrompt extends Partial<InsufficientCreditsDetail> {
  /** 自定义说明（可选；默认按 required/available 生成） */
  reason?: string
}

type Listener = (prompt: CreditsPrompt) => void
const listeners = new Set<Listener>()

/**
 * 全局入口：任何地方（含 toastApiError 收到 402）都可以调用，
 * 由挂在 AppLayout 里的 <CreditsDialogHost /> 负责显示。
 */
export function openCreditsDialog(prompt: CreditsPrompt) {
  listeners.forEach((fn) => fn(prompt))
}

function describe(p: CreditsPrompt): string {
  if (p.reason) return p.reason
  if (p.required != null && p.available != null) {
    return `这次操作需要 ${p.required} 积分，你当前可用 ${p.available} 积分。充值后即可继续；每天也会再送一笔免费积分。`
  }
  return '积分不足。充值后即可继续；每天也会再送一笔免费积分。'
}

interface CreditsDialogProps {
  prompt: CreditsPrompt | null
  onClose: () => void
}

/** 余额不足 → 去充值。取代旧的 UpgradeDialog（会员制）。 */
export function CreditsDialog({ prompt, onClose }: CreditsDialogProps) {
  const navigate = useNavigate()
  return (
    <Dialog open={prompt !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-[380px]">
        <DialogHeader>
          <DialogTitle>积分不足</DialogTitle>
          <DialogDescription>{prompt ? describe(prompt) : ''}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            暂不
          </Button>
          <Button
            onClick={() => {
              onClose()
              navigate(PATHS.credits)
            }}
          >
            去充值
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/** 挂一次（AppLayout）。监听 openCreditsDialog()。 */
export function CreditsDialogHost() {
  const [prompt, setPrompt] = useState<CreditsPrompt | null>(null)
  useEffect(() => {
    const fn: Listener = (p) => setPrompt(p)
    listeners.add(fn)
    return () => {
      listeners.delete(fn)
    }
  }, [])
  return <CreditsDialog prompt={prompt} onClose={() => setPrompt(null)} />
}
