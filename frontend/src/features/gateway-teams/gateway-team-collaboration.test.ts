import { describe, expect, it } from 'vitest'

import type { GatewayTeam } from '@/api/gateway/teams'

import {
  filterCollaborationGatewayTeams,
  isCollaborationGatewayTeam,
} from './gateway-team-collaboration'

const personal: GatewayTeam = {
  id: 'p1',
  name: '个人工作区',
  slug: 'personal-u1',
  kind: 'personal',
  owner_user_id: 'u1',
  team_role: 'owner',
}

const shared: GatewayTeam = {
  id: 's1',
  name: 'Alpha',
  slug: 'alpha',
  kind: 'shared',
  owner_user_id: 'u1',
  team_role: 'admin',
}

describe('gateway-team-collaboration', () => {
  it('isCollaborationGatewayTeam excludes personal', () => {
    expect(isCollaborationGatewayTeam(personal)).toBe(false)
    expect(isCollaborationGatewayTeam(shared)).toBe(true)
  })

  it('filterCollaborationGatewayTeams keeps shared only', () => {
    expect(filterCollaborationGatewayTeams([personal, shared]).map((t) => t.id)).toEqual(['s1'])
  })
})
