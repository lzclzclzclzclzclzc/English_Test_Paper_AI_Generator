import { apiFetch } from '@/api/client'
import type { WritingGradeRequest, WritingGradeResponse } from '@/types/api'

/** 提交作文批改（独立于客观题判分）。 */
export const gradeWriting = (req: WritingGradeRequest) =>
  apiFetch<WritingGradeResponse>('/writing/grade', { method: 'POST', body: JSON.stringify(req) })

/** 获取某张试卷的历史写作批改结果（含用户作文文本、分数、详情）。 */
export const getWritingGradeHistory = (paper_id: string) =>
  apiFetch<WritingGradeResponse | null>(`/writing/by-paper/${paper_id}`, { method: 'GET' })