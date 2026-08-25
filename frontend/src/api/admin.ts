import { apiFetch } from '@/api/client'
import type {
  AdminAnalytics, AdminAuditList, AdminCreditAccount, AdminCreditAccountDetail, AdminCreditAccountList, AdminOrderList,
  AdminOverview, AdminRevenue, AdminSystemHealth, AdminTimeseries, AdminUsage, AdminUserAnalytics,
  AdminUserAttemptList, AdminUserDetail, AdminUserList, AdminUserPaperList, MasteryProfile,
  QuestionBankList, QuestionBankStats, User,
} from '@/types/api'

const qs = (params: Record<string, string | number | undefined>) => {
  const s = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== '') s.set(k, String(v))
  const out = s.toString()
  return out ? `?${out}` : ''
}

// 用户 / 统计 → 主后端 (/api)
export const listUsers = (
  q = '', limit = 50, offset = 0, status = '', sort = 'created_at',
  role = '', created_from = '', created_to = '',
) =>
  apiFetch<AdminUserList>(`/admin/users${qs({ q, limit, offset, status, sort, role, created_from, created_to })}`)
export const getUserDetail = (id: string) => apiFetch<AdminUserDetail>(`/admin/users/${id}`)
export const setRole = (id: string, role: 'user' | 'admin') =>
  apiFetch<User>(`/admin/users/${id}/role`, { method: 'POST', body: JSON.stringify({ role }) })
export const resetPassword = (id: string, new_password: string) =>
  apiFetch<User>(`/admin/users/${id}/reset-password`, { method: 'POST', body: JSON.stringify({ new_password }) })
export const banUser = (id: string) => apiFetch<User>(`/admin/users/${id}/ban`, { method: 'POST' })
export const unbanUser = (id: string) => apiFetch<User>(`/admin/users/${id}/unban`, { method: 'POST' })
export const getOverview = () => apiFetch<AdminOverview>('/admin/stats/overview')
export const getTimeseries = (days = 30) => apiFetch<AdminTimeseries>(`/admin/stats/timeseries${qs({ days })}`)
// days=0 = 全部历史；直接拼串确保 0 也传出（不经 qs 的 falsy 过滤）。
export const getAnalytics = (days = 30) => apiFetch<AdminAnalytics>(`/admin/analytics?days=${days}`)
export const getUsageStats = (days = 30) => apiFetch<AdminUsage>(`/admin/stats/usage?days=${days}`)
export const getUserMastery = (id: string) => apiFetch<MasteryProfile>(`/admin/users/${id}/mastery`)
export const getUserAnalytics = (id: string, days = 30) =>
  apiFetch<AdminUserAnalytics>(`/admin/users/${id}/analytics?days=${days}`)

// 用户维度深挖（Spec H B）
export const getUserPapers = (id: string, limit = 10) =>
  apiFetch<AdminUserPaperList>(`/admin/users/${id}/papers${qs({ limit })}`)
export const getUserAttempts = (id: string, limit = 10) =>
  apiFetch<AdminUserAttemptList>(`/admin/users/${id}/attempts${qs({ limit })}`)

// 题库（Spec H C，只读）
export const getQuestionBankStats = () => apiFetch<QuestionBankStats>('/admin/questionbank/stats')
export const searchQuestionBank = (
  params: { type?: string; kp?: string; book?: string; chapter?: string; q?: string; limit?: number; offset?: number },
) => apiFetch<QuestionBankList>(`/admin/questionbank/questions${qs(params)}`)

// 收入 / 审计 / 系统健康（Spec H D）
export const getRevenue = (days = 30) => apiFetch<AdminRevenue>(`/admin/stats/revenue${qs({ days })}`)
export const listAuditLogs = (actor = '', action = '', limit = 50, offset = 0) =>
  apiFetch<AdminAuditList>(`/admin/audit${qs({ actor, action, limit, offset })}`)
export const getSystemHealth = () => apiFetch<AdminSystemHealth>('/admin/system/health')

// 积分 / 订单（2026-08 纯积分制，本地账本）
export const listCreditAccounts = (q = '', limit = 50, offset = 0) =>
  apiFetch<AdminCreditAccountList>(`/admin/credits${qs({ q, limit, offset })}`)
export const getCreditAccount = (id: string, limit = 50, offset = 0) =>
  apiFetch<AdminCreditAccountDetail>(`/admin/credits/${id}${qs({ limit, offset })}`)
export const adjustCredits = (id: string, delta: number, note: string) =>
  apiFetch<AdminCreditAccount>(`/admin/credits/${id}/adjust`, { method: 'POST', body: JSON.stringify({ delta, note }) })
export const adjustCreditsByUsername = (username: string, delta: number, note: string) =>
  apiFetch<AdminCreditAccount>('/admin/credits/adjust', { method: 'POST', body: JSON.stringify({ username, delta, note }) })
export const listOrders = (
  params: {
    status?: string
    order_no?: string
    user?: string
    pack_id?: string
    created_from?: string
    created_to?: string
    paid_from?: string
    paid_to?: string
    limit?: number
    offset?: number
  } = {},
) => apiFetch<AdminOrderList>(`/admin/orders${qs({ limit: 50, offset: 0, ...params })}`)
export const reconcileOrders = () =>
  apiFetch<{ reconciled: number }>('/admin/orders/reconcile', { method: 'POST' })
