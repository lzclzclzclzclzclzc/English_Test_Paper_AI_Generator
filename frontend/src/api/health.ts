export interface ReadinessResponse {
  status: 'ready' | 'not_ready'
  checks: Record<string, boolean>
}

/**
 * readiness 检查（backend-api.md § 健康检查）：not_ready 时 HTTP 503 但 body 仍是
 * ReadinessResponse，所以不走 apiFetch 的抛错路径；网络/解析失败返回 null——
 * 该检查只用于温和提示，绝不打扰正常流程。
 */
export async function getReadiness(): Promise<ReadinessResponse | null> {
  try {
    const res = await fetch('/api/health/ready', { credentials: 'include' })
    return (await res.json()) as ReadinessResponse
  } catch {
    return null
  }
}
