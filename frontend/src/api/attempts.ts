import { apiFetch } from '@/api/client'
import type { GradeSubmissionRequest, GradeSubmissionResponse } from '@/types/api'

/**
 * 提交答题并判分。items 必须覆盖试卷全部 index 恰好一次（缺/重/多 → 422）。
 * 同一试卷允许重复提交，每次生成新 attempt_id。
 */
export const submitAttempt = (req: GradeSubmissionRequest) =>
  apiFetch<GradeSubmissionResponse>('/attempts', { method: 'POST', body: JSON.stringify(req) })

/** 取该试卷最新一次答题结果（用于复盘展示），未提交过返回 null。 */
export const getAttemptByPaper = (paperId: string) =>
  apiFetch<GradeSubmissionResponse | null>(`/attempts/by-paper/${paperId}`)
