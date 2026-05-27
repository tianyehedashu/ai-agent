import { describe, expect, it } from 'vitest'

import type { GatewayTeam } from '@/api/gateway/teams'

import {
  resolveMembersPageFallbackTeamId,
  resolveMembersPageTeamId,
} from './resolve-members-page-team-id'

const personal: GatewayTeam = {
  id: 'p1',
  name: '个人工作区',
  slug: 'personal-u1',
  kind: 'personal',
  owner_user_id: 'u1',
  team_role: 'owner',
}

const sharedA: GatewayTeam = {
  id: 's1',
  name: 'Alpha',
  slug: 'alpha',
  kind: 'shared',
  owner_user_id: 'u1',
  team_role: 'owner',
}

const sharedB: GatewayTeam = {
  id: 's2',
  name: 'Beta',
  slug: 'beta',
  kind: 'shared',
  owner_user_id: 'u1',
  team_role: 'member',
}

describe('resolveMembersPageTeamId', () => {
  it('redirects personal team to first shared team', () => {
    expect(resolveMembersPageTeamId('p1', [personal, sharedA, sharedB])).toBe('s1')
  })

  it('returns null when current team is already shared', () => {
    expect(resolveMembersPageTeamId('s2', [personal, sharedA, sharedB])).toBeNull()
  })

  it('returns null when only personal team exists', () => {
    expect(resolveMembersPageTeamId('p1', [personal])).toBeNull()
  })
})

describe('resolveMembersPageFallbackTeamId', () => {
  it('prefers first shared team after delete/leave', () => {
    expect(resolveMembersPageFallbackTeamId([personal, sharedB])).toBe('s2')
  })

  it('returns null when no shared teams remain', () => {
    expect(resolveMembersPageFallbackTeamId([personal])).toBeNull()
  })
})
