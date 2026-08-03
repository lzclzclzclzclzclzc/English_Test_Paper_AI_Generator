import { apiFetch } from '@/api/client'
import type {
  AdminAnalytics, AdminMembership, AdminMembershipList, AdminOrderList, AdminOverview,
  AdminTimeseries, AdminUserDetail, AdminUserList, MasteryProfile, User,
} from '@/types/api'

const qs = (params: Record<string, string | number | undefined>) => {
  const s = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== '') s.set(k, String(v))
  const out = s.toString()
  return out ? `?${out}` : ''
}

// 用户 / 统计 → 主后端 (/api)
export const listUsers = (q = '', limit = 50, offset = 0) =>
  apiFetch<AdminUserList>(`/admin/users${qs({ q, limit, offset })}`)
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

// 会员 / 订单 → 主后端聚合端点 (/api，补齐 username)
export const listMemberships = (q = '', limit = 50, offset = 0) =>
  apiFetch<AdminMembershipList>(`/admin/memberships${qs({ q, limit, offset })}`)
export const grantMembership = (id: string, body: { days?: number; plan_id?: string }) =>
  apiFetch<AdminMembership>(`/admin/memberships/${id}/grant`, { method: 'POST', body: JSON.stringify(body) })
export const revokeMembership = (id: string) =>
  apiFetch<AdminMembership>(`/admin/memberships/${id}/revoke`, { method: 'POST' })
export const grantMembershipByUsername = (username: string, days: number) =>
  apiFetch<AdminMembership>('/admin/memberships/grant', { method: 'POST', body: JSON.stringify({ username, days }) })
export const listOrders = (status = '', limit = 50, offset = 0) =>
  apiFetch<AdminOrderList>(`/admin/orders${qs({ status, limit, offset })}`)
