import { describe, expect, it } from 'vitest'

import type { GatewayTeam } from '@/api/gateway/teams'

import { gatewayTeamDisplayLabel, gatewayTeamRoleSubtitle } from './gateway-team-display'

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

describe('gatewayTeamDisplayLabel', () => {
  it('uses personal workspace label', () => {
    expect(gatewayTeamDisplayLabel(team({ id: 'p1', kind: 'personal', name: 'Personal' }))).toBe(
      '个人工作区'
    )
  })
})

describe('gatewayTeamRoleSubtitle', () => {
  it('shows platform bypass for admin on member-only membership', () => {
    expect(gatewayTeamRoleSubtitle(team({ id: 'm1', team_role: 'member' }), true)).toBe('平台')
  })

  it('shows owner label for platform admin who is team owner', () => {
    expect(gatewayTeamRoleSubtitle(team({ id: 'o1', team_role: 'owner' }), true)).toBe('所有者')
  })
})
