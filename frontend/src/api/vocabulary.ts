import { apiFetch } from '@/api/client'
import type {
  VocabularyProgress,
  VocabularyRating,
  VocabularyReviewResponse,
  VocabularyToday,
} from '@/types/api'

export const getVocabularyToday = () => apiFetch<VocabularyToday>('/vocabulary/today')
export const getVocabularyProgress = () => apiFetch<VocabularyProgress>('/vocabulary/progress')

export const reviewVocabulary = (body: { word_id: string; answer: string; rating: VocabularyRating }) =>
  apiFetch<VocabularyReviewResponse>('/vocabulary/reviews', {
    method: 'POST',
    body: JSON.stringify(body),
  })

export const updateVocabularySettings = (daily_new_limit: number) =>
  apiFetch<{ daily_new_limit: number }>('/vocabulary/settings', {
    method: 'PATCH',
    body: JSON.stringify({ daily_new_limit }),
  })
