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

/** 列表页暂未做 UI，为将来 /papers 预留。 */
export const listPapers = (limit = 100, offset = 0) =>
  apiFetch<PaperListResponse>(`/papers?limit=${limit}&offset=${offset}`)
