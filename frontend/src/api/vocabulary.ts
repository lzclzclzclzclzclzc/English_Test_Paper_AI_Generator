import { apiFetch } from '@/api/client'
import type {
  VocabularyDailyResponse,
  VocabularyExampleResponse,
  VocabularyProgress,
  VocabularyRating,
  VocabularyJudgmentResponse,
  VocabularyToday,
} from '@/types/api'

export const getVocabularyToday = () => apiFetch<VocabularyToday>('/vocabulary/today')
export const getVocabularyProgress = () => apiFetch<VocabularyProgress>('/vocabulary/progress')
export const getVocabularyDaily = (days = 30) =>
  apiFetch<VocabularyDailyResponse>(`/vocabulary/daily?days=${days}`)

export const judgeVocabulary = (body: { word_id: string; rating: VocabularyRating }) =>
  apiFetch<VocabularyJudgmentResponse>('/vocabulary/judgments', {
    method: 'POST',
    body: JSON.stringify(body),
  })

export const updateVocabularySettings = (daily_new_limit: number) =>
  apiFetch<{ daily_new_limit: number; today_new_cards_added: number }>('/vocabulary/settings', {
    method: 'PATCH',
    body: JSON.stringify({ daily_new_limit }),
  })

export const generateVocabularyExample = (word_id: string) =>
  apiFetch<VocabularyExampleResponse>('/vocabulary/example', {
    method: 'POST',
    body: JSON.stringify({ word_id }),
  })
