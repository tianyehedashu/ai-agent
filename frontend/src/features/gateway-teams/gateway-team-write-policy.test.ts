import { describe, expect, it } from 'vitest'

import type { GatewayTeam } from '@/api/gateway/teams'

import { filterGatewayWritableTeams, isGatewayTeamWritable } from './gateway-team-write-policy'

function team(partial: Partial<GatewayTeam> & Pick<GatewayTeam, 'id'>): GatewayTeam {
  return {
    id: partial.id,
    name: partial.name ?? 'Team',
    slug: partial.slug ?? 'team',
    kind: partial.kind ?? 'shared',
    owner_user_id: partial.owner_user_id ?? 'owner-1',
    team_role: partial.team_role,
  }
}

describe('isGatewayTeamWritable', () => {
  it('allows all teams for platform admin', () => {
    const memberTeam = team({ id: 't1', team_role: 'member' })
    expect(isGatewayTeamWritable(memberTeam, true)).toBe(true)
  })

  it('allows platform admin to write shared member team in filter', () => {
    const teams = [team({ id: 'm1', team_role: 'member' })]
    expect(filterGatewayWritableTeams(teams, true)).toHaveLength(1)
  })

  it('allows personal team for regular user', () => {
    expect(isGatewayTeamWritable(team({ id: 'p1', kind: 'personal' }), false)).toBe(true)
  })

  it('allows shared owner/admin and rejects member', () => {
    expect(isGatewayTeamWritable(team({ id: 'o1', team_role: 'owner' }), false)).toBe(true)
    expect(isGatewayTeamWritable(team({ id: 'a1', team_role: 'admin' }), false)).toBe(true)
    expect(isGatewayTeamWritable(team({ id: 'm1', team_role: 'member' }), false)).toBe(false)
  })
})

describe('filterGatewayWritableTeams', () => {
  it('filters member teams for non-admin', () => {
    const teams = [
      team({ id: 'p1', kind: 'personal' }),
      team({ id: 'a1', team_role: 'admin' }),
      team({ id: 'm1', team_role: 'member' }),
    ]
    expect(filterGatewayWritableTeams(teams, false).map((t) => t.id)).toEqual(['p1', 'a1'])
  })
})
