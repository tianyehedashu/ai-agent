import { describe, expect, it } from 'vitest'

import { buildManagedTeamRouteUsageKey, buildRouteUsageKey } from './usage-keys'

describe('usage-keys', () => {
  it('buildRouteUsageKey returns route name for single-tenant lists', () => {
    expect(buildRouteUsageKey('gpt-4o-chat')).toBe('gpt-4o-chat')
  })

  it('buildManagedTeamRouteUsageKey scopes route by team', () => {
    const teamA = '11111111-1111-1111-1111-111111111111'
    const teamB = '22222222-2222-2222-2222-222222222222'
    expect(buildManagedTeamRouteUsageKey(teamA, 'shared-name')).toBe(`${teamA}:shared-name`)
    expect(buildManagedTeamRouteUsageKey(teamB, 'shared-name')).toBe(`${teamB}:shared-name`)
    expect(buildManagedTeamRouteUsageKey(teamA, 'shared-name')).not.toBe(
      buildManagedTeamRouteUsageKey(teamB, 'shared-name')
    )
  })
})
