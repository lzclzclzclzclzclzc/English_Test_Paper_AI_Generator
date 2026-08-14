import { apiFetch } from '@/api/client'
import type {
  GeneratePaperRequest,
  Paper,
  PaperListResponse,
  RevisePaperRequest,
} from '@/types/api'

export const generatePaper = (req: GeneratePaperRequest) =>
  apiFetch<Paper>('/papers/generate', { method: 'POST', body: JSON.stringify(req) })

/** 返回全新 paper_id 的 Paper，原试卷仍存在。 */
export const revisePaper = (req: RevisePaperRequest) =>
  apiFetch<Paper>('/papers/revise', { method: 'POST', body: JSON.stringify(req) })

export const getPaper = (paperId: string) => apiFetch<Paper>(`/papers/${paperId}`)

/** 历史试卷筛选（服务端 GET /api/papers 查询参数；未定义即不筛）。 */
export interface PaperFilters {
  submitted?: boolean
  question_type?: string
  start_date?: string // YYYY-MM-DD
  end_date?: string // YYYY-MM-DD
}

/** 列表只返回摘要（无题面、无总数）；PapersPage 以"满页即有下一页"翻页。 */
export const listPapers = (limit = 100, offset = 0, filters: PaperFilters = {}) => {
  const p = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  if (filters.submitted !== undefined) p.set('submitted', String(filters.submitted))
  if (filters.question_type) p.set('question_type', filters.question_type)
  if (filters.start_date) p.set('start_date', filters.start_date)
  if (filters.end_date) p.set('end_date', filters.end_date)
  return apiFetch<PaperListResponse>(`/papers?${p.toString()}`)
}
