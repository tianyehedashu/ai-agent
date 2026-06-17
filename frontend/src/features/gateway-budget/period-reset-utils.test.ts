import { describe, expect, it } from 'vitest'

import {
  formatPeriodResetLabel,
  isCalendarPeriodResetVisible,
  isMonthlyPeriodReset,
  minutesToTimeString,
  timeStringToMinutes,
} from './period-reset-utils'

describe('period-reset-utils', () => {
  it('converts minutes and time strings', () => {
    expect(minutesToTimeString(0)).toBe('00:00')
    expect(minutesToTimeString(9 * 60 + 30)).toBe('09:30')
    expect(timeStringToMinutes('09:30')).toBe(570)
    expect(timeStringToMinutes('invalid')).toBeNull()
  })

  it('formats daily and monthly labels', () => {
    expect(
      formatPeriodResetLabel(
        { period_timezone: 'Asia/Shanghai', period_reset_minutes: 540 },
        'daily'
      )
    ).toBe('每日 09:00 (Asia/Shanghai)')
    expect(
      formatPeriodResetLabel(
        { period_timezone: 'UTC', period_reset_minutes: 0, period_reset_day: 31 },
        'monthly'
      )
    ).toBe('每月 31 日 00:00 (UTC)（短月按月末）')
  })

  it('detects calendar reset visibility', () => {
    expect(isCalendarPeriodResetVisible({ layer: 'platform', period: 'daily' })).toBe(true)
    expect(isCalendarPeriodResetVisible({ layer: 'platform', period: 'total' })).toBe(false)
    expect(isCalendarPeriodResetVisible({ layer: 'upstream', windowSeconds: '86400' })).toBe(true)
    expect(isCalendarPeriodResetVisible({ layer: 'upstream', windowSeconds: '3600' })).toBe(false)
  })

  it('detects monthly reset', () => {
    expect(isMonthlyPeriodReset({ layer: 'platform', period: 'monthly' })).toBe(true)
    expect(isMonthlyPeriodReset({ layer: 'upstream', windowSeconds: '2592000' })).toBe(true)
    expect(isMonthlyPeriodReset({ layer: 'upstream', windowSeconds: '86400' })).toBe(false)
  })
})
