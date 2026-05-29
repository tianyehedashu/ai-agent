import { describe, expect, it } from 'vitest'

import {
  gatewayUsageAggregationOptions,
  isCrossTeamUsageStatsEnabled,
  usageAggregationScopeLabel,
} from './usage-aggregation'

describe('isCrossTeamUsageStatsEnabled', () => {
  it('returns true for user aggregation', () => {
    expect(isCrossTeamUsageStatsEnabled('user')).toBe(true)
  })

  it('returns true for platform aggregation', () => {
    expect(isCrossTeamUsageStatsEnabled('platform')).toBe(true)
  })

  it('returns false for workspace aggregation', () => {
    expect(isCrossTeamUsageStatsEnabled('workspace')).toBe(false)
  })
})

describe('usageAggregationScopeLabel', () => {
  it('maps each aggregation to scope copy', () => {
    expect(usageAggregationScopeLabel('platform')).toBe('全平台调用')
    expect(usageAggregationScopeLabel('user')).toBe('我的跨团队调用')
    expect(usageAggregationScopeLabel('workspace')).toBe('当前团队调用')
  })
})

describe('gatewayUsageAggregationOptions', () => {
  it('exposes platform option only to platform admins', () => {
    const adminValues = gatewayUsageAggregationOptions(true).map((o) => o.value)
    expect(adminValues).toContain('platform')

    const memberValues = gatewayUsageAggregationOptions(false).map((o) => o.value)
    expect(memberValues).not.toContain('platform')
    expect(memberValues).toEqual(['workspace', 'user'])
  })
})
