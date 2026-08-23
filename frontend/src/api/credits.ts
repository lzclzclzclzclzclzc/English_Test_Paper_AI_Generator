import { apiFetch } from '@/api/client'
import type { CreditAccount, CreditLedgerList, CreditPriceTable } from '@/types/payment'

export const getMyCredits = () => apiFetch<CreditAccount>('/credits/me')

export const getCreditPrices = () => apiFetch<CreditPriceTable>('/credits/prices')

export const getCreditLedger = (limit = 50, offset = 0) =>
  apiFetch<CreditLedgerList>(`/credits/ledger?limit=${limit}&offset=${offset}`)
