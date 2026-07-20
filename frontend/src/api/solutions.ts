import { apiFetch } from '@/api/client'
import type { SolutionRequest, SolutionResponse } from '@/types/api'

/** 按需生成单题解析（限流 60/min，调用方注意缓存）。 */
export const fetchSolution = (req: SolutionRequest) =>
  apiFetch<SolutionResponse>('/solutions', { method: 'POST', body: JSON.stringify(req) })
