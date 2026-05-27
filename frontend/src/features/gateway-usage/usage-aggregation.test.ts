import { describe, expect, it } from 'vitest'

import { isCrossTeamUsageStatsEnabled } from './usage-aggregation'

describe('isCrossTeamUsageStatsEnabled', () => {
  it('returns true for user aggregation', () => {
    expect(isCrossTeamUsageStatsEnabled('user')).toBe(true)
  })

  it('returns false for workspace aggregation', () => {
    expect(isCrossTeamUsageStatsEnabled('workspace')).toBe(false)
  })
})
