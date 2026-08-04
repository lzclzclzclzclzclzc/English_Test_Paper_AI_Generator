import { describe, expect, it } from 'vitest'
import { adminGuardState } from '@/components/requireAdmin.logic'

describe('adminGuardState', () => {
  it('loading when user is undefined', () => {
    expect(adminGuardState(undefined)).toBe('loading')
  })
  it('redirect when logged out', () => {
    expect(adminGuardState(null)).toBe('redirect')
  })
  it('redirect when non-admin', () => {
    expect(adminGuardState({ role: 'user' })).toBe('redirect')
  })
  it('allow when admin', () => {
    expect(adminGuardState({ role: 'admin' })).toBe('allow')
  })
})
