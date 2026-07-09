import { apiFetch } from '@/api/client'
import type { GradeSubmissionRequest, GradeSubmissionResponse } from '@/types/api'

/**
 * 提交答题并判分。items 必须覆盖试卷全部 index 恰好一次（缺/重/多 → 422）。
 * 同一试卷允许重复提交，每次生成新 attempt_id。
 */
export const submitAttempt = (req: GradeSubmissionRequest) =>
  apiFetch<GradeSubmissionResponse>('/attempts', { method: 'POST', body: JSON.stringify(req) })
