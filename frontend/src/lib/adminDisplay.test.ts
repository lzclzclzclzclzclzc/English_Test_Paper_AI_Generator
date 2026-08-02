import { describe, expect, it } from 'vitest'
import { displayName } from './adminDisplay'

describe('displayName', () => {
  it('returns the username when present', () => {
    expect(displayName('alice')).toBe('alice')
  })

  it('falls back to placeholder for null', () => {
    expect(displayName(null)).toBe('(已删除/未知)')
  })

  it('falls back to placeholder for empty string', () => {
    expect(displayName('')).toBe('(已删除/未知)')
  })

  it('falls back to placeholder for whitespace-only string', () => {
    expect(displayName('  ')).toBe('(已删除/未知)')
  })
})
