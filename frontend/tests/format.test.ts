import { describe, expect, it } from 'vitest'
import { fmt } from '../src/shared/lib/format'

describe('missing numerical data', () => {
  it('never substitutes zero for unavailable metrics', () => {
    expect(fmt(null)).toBe('нет данных')
    expect(fmt(undefined)).toBe('нет данных')
    expect(fmt(0)).toBe('0')
  })
  it('uses Russian decimal notation', () => {
    expect(fmt(0.75, 2)).toBe('0,75')
  })
})
