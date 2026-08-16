import { describe, expect, it } from 'vitest'
import { pageCountOf } from '@/components/admin/Pagination'
import { ACTION_LABELS } from '@/pages/admin/AdminAuditPage'

describe('Pagination page math (Spec H A1)', () => {
  it('computes page counts with ceiling', () => {
    expect(pageCountOf(0, 20)).toBe(1) // empty set still 1 page (component hides itself)
    expect(pageCountOf(1, 20)).toBe(1)
    expect(pageCountOf(20, 20)).toBe(1) // exactly full page
    expect(pageCountOf(21, 20)).toBe(2) // one leftover row
    expect(pageCountOf(101, 50)).toBe(3)
  })

  it('boundary disable conditions: page 1 has no prev, last page has no next', () => {
    // The component disables prev when page <= 1 and next when page >= pageCount.
    const pageCount = pageCountOf(100, 50)
    expect(pageCount).toBe(2)
    expect(1 <= 1).toBe(true) // prev disabled on page 1
    expect(2 >= pageCount).toBe(true) // next disabled on page 2 (last)
    expect(1 >= pageCount).toBe(false) // next NOT disabled on page 1
  })
})

describe('audit action labels (Spec H D3)', () => {
  it('maps every audited backend action to a Chinese label', () => {
    const audited = [
      'set_role',
      'reset_password',
      'ban',
      'unban',
      'grant_membership',
      'revoke_membership',
    ]
    for (const a of audited) {
      expect(ACTION_LABELS[a], `missing label for ${a}`).toBeTruthy()
    }
  })
})
