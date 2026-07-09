import { apiFetch } from '@/api/client'
import type { MasteryProfile } from '@/types/api'

export const getMastery = (windowDays?: number) =>
  apiFetch<MasteryProfile>(
    windowDays != null ? `/users/me/mastery?window_days=${windowDays}` : '/users/me/mastery',
  )
