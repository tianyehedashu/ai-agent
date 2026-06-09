import { describe, expect, it } from 'vitest'

import {
  usageStatsCustomDateRange,
  usageStatsDateRangeToQuery,
  usageStatsPresetDateRange,
} from './usage-stats-date-range'

describe('usageStatsDateRangeToQuery', () => {
  it('uses days for preset ranges', () => {
    const selection = usageStatsPresetDateRange(30, new Date(2026, 5, 9, 12))

    expect(selection).toEqual({
      presetDays: 30,
      startDate: '2026-05-10',
      endDate: '2026-06-09',
    })
    expect(usageStatsDateRangeToQuery(selection)).toEqual({ days: 30 })
  })

  it('uses local full-day ISO bounds for custom ranges', () => {
    const selection = usageStatsCustomDateRange('2026-01-01', '2026-01-03')
    const query = usageStatsDateRangeToQuery(selection)

    expect(query.days).toBeUndefined()
    expect(new Date(query.start ?? '').getTime()).toBe(new Date(2026, 0, 1).getTime())
    expect(new Date(query.end ?? '').getTime()).toBe(
      new Date(2026, 0, 3, 23, 59, 59, 999).getTime()
    )
  })

  it('clamps inverted custom ranges to a single date', () => {
    const selection = usageStatsCustomDateRange('2026-01-05', '2026-01-03')

    expect(selection).toEqual({
      presetDays: null,
      startDate: '2026-01-03',
      endDate: '2026-01-03',
    })
  })
})
