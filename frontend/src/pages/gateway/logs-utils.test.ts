import { describe, expect, it } from 'vitest'

import { isValidDateRangeValue, resolveDateRange } from './logs-utils'

describe('resolveDateRange', () => {
  it('returns start 1 hour ago for "1h"', () => {
    const before = new Date()
    const result = resolveDateRange('1h')
    const after = new Date()

    expect(result.end.getTime()).toBeGreaterThanOrEqual(before.getTime())
    expect(result.end.getTime()).toBeLessThanOrEqual(after.getTime())

    const expectedStart = new Date(result.end)
    expectedStart.setHours(expectedStart.getHours() - 1)
    expect(result.start.getTime()).toBe(expectedStart.getTime())
  })

  it('returns start of today for "today"', () => {
    const result = resolveDateRange('today')
    const expectedStart = new Date(result.end)
    expectedStart.setHours(0, 0, 0, 0)
    expect(result.start.getTime()).toBe(expectedStart.getTime())
  })

  it('returns start 7 days ago for "7d"', () => {
    const result = resolveDateRange('7d')
    const expectedStart = new Date(result.end)
    expectedStart.setDate(expectedStart.getDate() - 7)
    expect(result.start.getTime()).toBe(expectedStart.getTime())
  })

  it('returns start 30 days ago for "30d"', () => {
    const result = resolveDateRange('30d')
    const expectedStart = new Date(result.end)
    expectedStart.setDate(expectedStart.getDate() - 30)
    expect(result.start.getTime()).toBe(expectedStart.getTime())
  })
})

describe('isValidDateRangeValue', () => {
  it('returns true for valid values', () => {
    expect(isValidDateRangeValue('1h')).toBe(true)
    expect(isValidDateRangeValue('today')).toBe(true)
    expect(isValidDateRangeValue('7d')).toBe(true)
    expect(isValidDateRangeValue('30d')).toBe(true)
  })

  it('returns false for invalid values', () => {
    expect(isValidDateRangeValue('')).toBe(false)
    expect(isValidDateRangeValue('invalid')).toBe(false)
    expect(isValidDateRangeValue('1d')).toBe(false)
    expect(isValidDateRangeValue(null)).toBe(false)
  })
})
