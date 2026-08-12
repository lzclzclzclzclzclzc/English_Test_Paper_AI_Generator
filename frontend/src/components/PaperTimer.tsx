import { useEffect, useRef, useState } from 'react'
import { cn } from '@/lib/utils'

interface PaperTimerProps {
  minutes: number
  /** false（判分中/复盘）时冻结走秒 */
  running: boolean
  /** 倒数到 0 时触发一次（提醒，不强制收卷） */
  onExpire: () => void
}

/**
 * 倒计时显示「剩余 MM:SS」：作答态每秒 tick，最后 5 分钟转赤陶；
 * 到 0 只触发一次 onExpire，之后停在 00:00。
 */
export function PaperTimer({ minutes, running, onExpire }: PaperTimerProps) {
  const [secondsLeft, setSecondsLeft] = useState(() => Math.max(0, Math.round(minutes * 60)))
  const expiredRef = useRef(false)
  const onExpireRef = useRef(onExpire)
  useEffect(() => {
    onExpireRef.current = onExpire
  }, [onExpire])

  useEffect(() => {
    if (!running) return
    const id = window.setInterval(() => {
      setSecondsLeft((s) => (s > 0 ? s - 1 : 0))
    }, 1000)
    return () => window.clearInterval(id)
  }, [running])

  useEffect(() => {
    if (secondsLeft === 0 && !expiredRef.current) {
      expiredRef.current = true
      onExpireRef.current()
    }
  }, [secondsLeft])

  const mm = String(Math.floor(secondsLeft / 60)).padStart(2, '0')
  const ss = String(secondsLeft % 60).padStart(2, '0')

  return (
    <span
      className={cn(
        'font-ui text-[13.5px] font-bold tabular-nums',
        secondsLeft <= 300 ? 'text-accent' : 'text-ink',
      )}
    >
      剩余 {mm}:{ss}
    </span>
  )
}
