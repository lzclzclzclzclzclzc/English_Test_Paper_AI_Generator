import { apiFetch } from '@/api/client'
import type { AgentChatRequest, AgentChatResponse, ExtractPlanRequest, StudyPlan } from '@/types/api'

export const agentChat = (req: AgentChatRequest) =>
  apiFetch<AgentChatResponse>('/agent/chat', {
    method: 'POST',
    body: JSON.stringify(req),
  })

export const extractStudyPlan = (req: ExtractPlanRequest) =>
  apiFetch<StudyPlan>('/agent/extract-plan', {
    method: 'POST',
    body: JSON.stringify(req),
  })

export const getLatestStudyPlan = () =>
  apiFetch<StudyPlan | null>('/agent/study-plans/latest')
