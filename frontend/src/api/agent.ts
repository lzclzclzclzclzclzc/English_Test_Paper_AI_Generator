import { apiFetch } from '@/api/client'
import type { AgentChatRequest, AgentChatResponse, StudyPlan } from '@/types/api'

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
