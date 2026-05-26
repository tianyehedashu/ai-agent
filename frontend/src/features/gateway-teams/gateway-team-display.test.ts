import { describe, expect, it } from 'vitest'

import type { GatewayTeam } from '@/api/gateway/teams'

import {
  gatewayCrossTeamOverviewTabLabel,
  gatewayTeamDisplayLabel,
  gatewayTeamRoleSubtitle,
} from './gateway-team-display'

function team(partial: Partial<GatewayTeam> & Pick<GatewayTeam, 'id'>): GatewayTeam {
  return {
    id: partial.id,
    name: partial.name ?? 'Team',
    slug: partial.slug ?? 'team',
    kind: partial.kind ?? 'shared',
    owner_user_id: partial.owner_user_id ?? 'owner-1',
    team_role: partial.team_role,
    owner_email: partial.owner_email,
    owner_name: partial.owner_name,
  }
}

describe('gatewayTeamDisplayLabel', () => {
  it('uses personal workspace label for viewer own team', () => {
    expect(
      gatewayTeamDisplayLabel(
        team({ id: 'p1', kind: 'personal', name: 'Personal', owner_user_id: 'u1' }),
        {
          viewerUserId: 'u1',
        }
      )
    ).toBe('个人工作区')
  })

  it('distinguishes foreign personal team with owner email', () => {
    expect(
      gatewayTeamDisplayLabel(
        team({
          id: 'p2',
          kind: 'personal',
          name: 'Personal',
          owner_user_id: 'u2',
          owner_email: 'alice@example.com',
        }),
        { viewerUserId: 'u1' }
      )
    ).toBe('个人 · alice@example.com')
  })
})

describe('gatewayCrossTeamOverviewTabLabel', () => {
  it('hides huge count for platform admin', () => {
    expect(gatewayCrossTeamOverviewTabLabel(935, true)).toBe('全平台汇总')
  })

  it('shows writable team count for team admin', () => {
    expect(gatewayCrossTeamOverviewTabLabel(3, false)).toBe('全部可管理 (3)')
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
