import { apiFetch } from '@/api/client'
import type {
  AgentChatRequest, AgentChatResponse, StudyPlan,
  MindmapListResponse, MindmapDetail,
} from '@/types/api'

export const agentChat = (req: AgentChatRequest) =>
  apiFetch<AgentChatResponse>('/agent/chat', {
    method: 'POST',
    body: JSON.stringify(req),
  })

/** 开始新对话：清空该用户在后端的会话历史。 */
export const clearAgentSession = () =>
  apiFetch<void>('/agent/chat/clear', { method: 'POST' })

export const getLatestStudyPlan = () =>
  apiFetch<StudyPlan | null>('/agent/study-plans/latest')

// ---- 思维导图 ----

export const listMindmaps = (limit = 20, offset = 0) =>
  apiFetch<MindmapListResponse>(`/agent/mindmaps?limit=${limit}&offset=${offset}`)

export const getMindmap = (id: string) =>
  apiFetch<MindmapDetail>(`/agent/mindmaps/${id}`)

export const createMindmap = (title: string, outline_md: string) =>
  apiFetch<{ id: string }>('/agent/mindmaps', {
    method: 'POST',
    body: JSON.stringify({ title, outline_md }),
  })

export const updateMindmap = (id: string, body: { title?: string; outline_md?: string }) =>
  apiFetch<MindmapDetail>(`/agent/mindmaps/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  })

export const deleteMindmap = (id: string) =>
  apiFetch<void>(`/agent/mindmaps/${id}`, { method: 'DELETE' })
