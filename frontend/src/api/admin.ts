import { apiFetch } from '@/api/client'
import type {
  AdminAnalytics, AdminAuditList, AdminMembership, AdminMembershipList, AdminOrderList,
  AdminOverview, AdminRevenue, AdminSystemHealth, AdminTimeseries, AdminUserAnalytics,
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
) =>
  apiFetch<AdminUserList>(`/admin/users${qs({ q, limit, offset, status, sort })}`)
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

// 会员 / 订单 → 主后端聚合端点 (/api，补齐 username)
export const listMemberships = (
  q = '', limit = 50, offset = 0, expiringWithinDays?: number, active?: boolean,
) =>
  apiFetch<AdminMembershipList>(`/admin/memberships${qs({
    q,
    limit,
    offset,
    expiring_within_days: expiringWithinDays,
    active: active === undefined ? undefined : String(active),
  })}`)
export const grantMembership = (id: string, body: { days?: number; plan_id?: string }) =>
  apiFetch<AdminMembership>(`/admin/memberships/${id}/grant`, { method: 'POST', body: JSON.stringify(body) })
export const revokeMembership = (id: string) =>
  apiFetch<AdminMembership>(`/admin/memberships/${id}/revoke`, { method: 'POST' })
export const grantMembershipByUsername = (username: string, days: number) =>
  apiFetch<AdminMembership>('/admin/memberships/grant', { method: 'POST', body: JSON.stringify({ username, days }) })
export const listOrders = (status = '', limit = 50, offset = 0) =>
  apiFetch<AdminOrderList>(`/admin/orders${qs({ status, limit, offset })}`)
