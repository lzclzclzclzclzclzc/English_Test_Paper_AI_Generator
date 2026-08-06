/**
 * 答题限时的 sessionStorage 交接（纯函数）。
 * 出卷入口（整卷模拟等）与试卷页不在同一路由：入口在 generate 前登记分钟数，
 * 试卷页挂载时一次性取走——取走即清除，刷新试卷页不会重启计时。
 */
const PENDING_KEY = 'mj.timer.pending'

/** 生成前调用：登记即将打开的卷子要限时多少分钟 */
export function setPendingTimer(minutes: number): void {
  sessionStorage.setItem(PENDING_KEY, String(minutes))
}

/** 试卷页挂载时调用：取走并清除（一次性，防刷新重启计时） */
export function claimPendingTimer(): number | null {
  const raw = sessionStorage.getItem(PENDING_KEY)
  if (raw === null) return null
  sessionStorage.removeItem(PENDING_KEY)
  const minutes = Number.parseInt(raw, 10)
  return Number.isFinite(minutes) && minutes > 0 ? minutes : null
}
