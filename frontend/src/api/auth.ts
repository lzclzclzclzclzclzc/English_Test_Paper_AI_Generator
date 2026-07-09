import { apiFetch, ApiError } from '@/api/client'
import type { User, UserCredentials } from '@/types/api'

/** 注册即自动登录（后端同时 Set-Cookie）。 */
export const register = (creds: UserCredentials) =>
  apiFetch<User>('/auth/register', { method: 'POST', body: JSON.stringify(creds) })

export const login = (creds: UserCredentials) =>
  apiFetch<User>('/auth/login', { method: 'POST', body: JSON.stringify(creds) })

export const logout = () => apiFetch<undefined>('/auth/logout', { method: 'POST' })

/**
 * 当前用户；未登录（401）返回 null 而不抛错——
 * 避免登录页上的重试风暴与 RequireAuth 跳转竞态（Spec D § 3.2）。
 */
export async function getMe(): Promise<User | null> {
  try {
    return await apiFetch<User>('/auth/me')
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return null
    throw err
  }
}
