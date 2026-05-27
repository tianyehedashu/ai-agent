/**
 * filterWritableTeamsBySearch — 单元测试。
 */

import { describe, expect, it } from 'vitest'

import type { GatewayTeam } from '@/api/gateway/teams'

import { filterWritableTeamsBySearch } from './filter-writable-teams-by-search'

const teamA: GatewayTeam = {
  id: 't1',
  name: 'Alpha Team',
  slug: 'alpha',
  kind: 'shared',
  owner_user_id: 'owner-1',
  team_role: 'admin',
}

const teamB: GatewayTeam = {
  id: 't2',
  name: 'Personal',
  slug: 'personal-user',
  kind: 'personal',
  owner_user_id: 'user-1',
  team_role: 'owner',
}

describe('filterWritableTeamsBySearch', () => {
  it('returns all teams when search is empty', () => {
    expect(filterWritableTeamsBySearch([teamA, teamB], '')).toEqual([teamA, teamB])
  })

  it('filters by display label or name', () => {
    expect(filterWritableTeamsBySearch([teamA, teamB], 'alpha')).toEqual([teamA])
    expect(filterWritableTeamsBySearch([teamA, teamB], '个人工作区', 'user-1')).toEqual([teamB])
    expect(filterWritableTeamsBySearch([teamA, teamB], 'personal')).toEqual([teamB])
  })
})
