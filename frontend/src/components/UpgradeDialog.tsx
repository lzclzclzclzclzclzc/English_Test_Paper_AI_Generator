import { useNavigate } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

/** 「会员」小标：标注会员专属功能（赤陶细边，One Chroma）。 */
export function MemberPill({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        'rounded-sm border border-accent/40 px-1.5 py-px font-ui text-[10px] leading-none text-accent',
        className,
      )}
    >
      会员
    </span>
  )
}

interface UpgradeDialogProps {
  /** 弹窗正文说明；为 null 时关闭。 */
  reason: string | null
  onClose: () => void
}

/** 非会员触碰会员功能时的升级引导。 */
export function UpgradeDialog({ reason, onClose }: UpgradeDialogProps) {
  const navigate = useNavigate()
  return (
    <Dialog open={reason !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-[380px]">
        <DialogHeader>
          <DialogTitle>会员功能</DialogTitle>
          <DialogDescription>{reason}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            暂不需要
          </Button>
          <Button
            onClick={() => {
              onClose()
              navigate('/membership')
            }}
          >
            去开通会员
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
