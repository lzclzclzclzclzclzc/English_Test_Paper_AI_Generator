import type { ErrorResponse } from '@/types/api'

/** 非 2xx 响应统一抛出；payload 为后端统一错误体。 */
export class ApiError extends Error {
  status: number
  payload: ErrorResponse

  constructor(status: number, payload: ErrorResponse) {
    super(payload.message)
    this.name = 'ApiError'
    this.status = status
    this.payload = payload
  }
}

/**
 * fetch 薄封装（Spec D § 5.1）：
 * - 前缀 /api（dev 走 vite proxy，prod 同源）
 * - 始终携带 Cookie
 * - 204 返回 undefined
 * - 非 2xx 抛 ApiError
 */
export async function apiFetch<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...opts,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...opts?.headers,
    },
  })
  if (res.status === 204) return undefined as T
  let body: unknown
  try {
    body = await res.json()
  } catch {
    // 非 JSON 响应（如代理层 502 的 HTML）：合成一个错误体
    body = {
      error_code: 'server.internal',
      message: `服务响应异常（HTTP ${res.status}）`,
      detail: null,
      trace_id: '',
    }
  }
  if (!res.ok) throw new ApiError(res.status, body as ErrorResponse)
  return body as T
}
