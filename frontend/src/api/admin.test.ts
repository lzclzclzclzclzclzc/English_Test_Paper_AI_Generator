import { describe, expect, it, vi, beforeEach } from 'vitest'
import {
  getUserAttempts,
  getUserPapers,
  adjustCredits,
  listAuditLogs,
  getRevenue,
  getSystemHealth,
  listUsers,
  searchQuestionBank,
} from '@/api/admin'

describe('admin api base-url routing', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('lists users via /api', async () => {
    const spy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ items: [], total: 0 }), { status: 200 }),
    )
    await listUsers('bob')
    expect(spy).toHaveBeenCalledWith(expect.stringContaining('/api/admin/users'), expect.anything())
  })

  it('adjusts credits via /api', async () => {
    const spy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ user_id: 'u', username: null, balance: 100, daily_balance: 30 }), { status: 200 }),
    )
    await adjustCredits('u', 100, '测试')
    expect(spy).toHaveBeenCalledWith(expect.stringContaining('/api/admin/credits/u/adjust'), expect.anything())
  })
})

describe('admin api spec-h endpoints (Spec H B/C/D)', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  const ok = (body: unknown) =>
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(body), { status: 200 }),
    )

  it('fetches user papers and attempts with limit', async () => {
    const spy = ok({ items: [] })
    await getUserPapers('u1', 10)
    await getUserAttempts('u1', 5)
    const urls = spy.mock.calls.map((c) => String(c[0]))
    expect(urls[0]).toBe('/api/admin/users/u1/papers?limit=10')
    expect(urls[1]).toBe('/api/admin/users/u1/attempts?limit=5')
  })

  it('searches question bank with filters (empty values dropped)', async () => {
    const spy = ok({ items: [], total: 0 })
    await searchQuestionBank({ type: 'word_form', q: 'past', limit: 20, offset: 40 })
    expect(spy).toHaveBeenCalledWith(
      '/api/admin/questionbank/questions?type=word_form&q=past&limit=20&offset=40',
      expect.anything(),
    )
  })

  it('drops empty filter params from question bank query', async () => {
    const spy = ok({ items: [], total: 0 })
    await searchQuestionBank({})
    expect(spy).toHaveBeenCalledWith('/api/admin/questionbank/questions', expect.anything())
  })

  it('fetches revenue, audit and system health', async () => {
    const spy = ok({ total_cents: 0, revenue_by_day: [], by_plan: [] })
    await getRevenue(30)
    await listAuditLogs('actor1', 'ban', 50, 100)
    await getSystemHealth()
    const urls = spy.mock.calls.map((c) => String(c[0]))
    expect(urls[0]).toBe('/api/admin/stats/revenue?days=30')
    expect(urls[1]).toBe('/api/admin/audit?actor=actor1&action=ban&limit=50&offset=100')
    expect(urls[2]).toBe('/api/admin/system/health')
  })
})
