import { describe, expect, it } from 'vitest'
import { shouldRedirectAdmin } from '@/components/redirectIfAdmin.logic'

describe('shouldRedirectAdmin', () => {
  it('true when admin', () => {
    expect(shouldRedirectAdmin({ role: 'admin' })).toBe(true)
  })
  it('false when non-admin user', () => {
    expect(shouldRedirectAdmin({ role: 'user' })).toBe(false)
  })
  it('false when logged out (null)', () => {
    expect(shouldRedirectAdmin(null)).toBe(false)
  })
  it('false when loading (undefined)', () => {
    expect(shouldRedirectAdmin(undefined)).toBe(false)
  })
})
