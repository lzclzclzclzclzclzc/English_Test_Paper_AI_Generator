import type { Intensity } from '@/lib/composeQuery'
import type { CreditAction } from '@/types/payment'

/** 改题强度 → 计价动作（镜像 backend/services/credits/pricing.py INTENSITY_ACTION） */
export const INTENSITY_ACTION: Record<Intensity, CreditAction> = {
  original: 'generate_original',
  light: 'generate_light',
  fresh: 'generate_fresh',
}
