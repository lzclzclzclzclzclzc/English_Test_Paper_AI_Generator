import { describe, expect, it, vi, beforeEach } from 'vitest'
import { listUsers, grantMembership } from '@/api/admin'

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

  it('grants membership via /payapi', async () => {
    const spy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ user_id: 'u', expires_at: null, active: true }), { status: 200 }),
    )
    await grantMembership('u', { days: 30 })
    expect(spy).toHaveBeenCalledWith(expect.stringContaining('/payapi/admin/memberships/u/grant'), expect.anything())
  })
})
