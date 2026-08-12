/**
 * 目标中考日期(localStorage,按用户隔离)。设置页写入,工作台读出倒计时。
 * 纯前端偏好,不进后端;克制呈现(一行小字),非游戏化。
 */
const keyOf = (userId: string) => `mj.examDate.${userId}`

/** 返回 'YYYY-MM-DD' 或 null(未设置/格式损坏) */
export function getExamDate(userId: string): string | null {
  const raw = localStorage.getItem(keyOf(userId))
  return raw && /^\d{4}-\d{2}-\d{2}$/.test(raw) ? raw : null
}

export function setExamDate(userId: string, date: string | null): void {
  if (date && /^\d{4}-\d{2}-\d{2}$/.test(date)) {
    localStorage.setItem(keyOf(userId), date)
  } else {
    localStorage.removeItem(keyOf(userId))
  }
}

/**
 * 距中考整天数(按本地日历日差):今天 = 0,明天 = 1;
 * 未设置或日期已过返回 null(过期不显示,不做负数提醒)。
 */
export function daysUntilExam(userId: string, now: Date = new Date()): number | null {
  const date = getExamDate(userId)
  if (!date) return null
  const [y, m, d] = date.split('-').map(Number)
  if (!y || !m || !d) return null
  const exam = new Date(y, m - 1, d)
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const diff = Math.round((exam.getTime() - today.getTime()) / 86_400_000)
  return diff >= 0 ? diff : null
}
