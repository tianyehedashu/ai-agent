/**
 * 协作团队候选解析 — 单元测试。
 */

import { describe, expect, it } from 'vitest'

import type { GatewayTeam } from '@/api/gateway/teams'

import {
  COLLABORATION_TEAMS_REQUIRE_SEARCH_THRESHOLD,
  groupResourcesByTenantId,
  resolveCollaborationTeamsCandidates,
} from './resolve-collaboration-teams-candidates'

function team(id: string, name: string): GatewayTeam {
  return {
    id,
    name,
    slug: name.toLowerCase(),
    kind: 'shared',
    owner_user_id: 'owner-1',
    team_role: 'owner',
  }
}

describe('resolveCollaborationTeamsCandidates', () => {
  it('returns sorted collaboration teams when under threshold', () => {
    const result = resolveCollaborationTeamsCandidates({
      isPlatformAdmin: false,
      hasSearch: false,
      queriedTeamCount: 2,
      candidateTeams: [team('t2', 'Beta'), team('t1', 'Alpha')],
      search: '',
    })
    expect(result.requiresSearch).toBe(false)
    expect(result.teams.map((t) => t.id)).toEqual(['t1', 't2'])
  })

  it('requires search for platform admin with many teams', () => {
    const result = resolveCollaborationTeamsCandidates({
      isPlatformAdmin: true,
      hasSearch: false,
      queriedTeamCount: COLLABORATION_TEAMS_REQUIRE_SEARCH_THRESHOLD + 1,
      candidateTeams: [],
      search: '',
    })
    expect(result.requiresSearch).toBe(true)
    expect(result.teams).toEqual([])
  })
})

describe('groupResourcesByTenantId', () => {
  it('groups items by tenant_id', () => {
    const map = groupResourcesByTenantId([
      { tenant_id: 't1', id: 'c1' },
      { tenant_id: 't2', id: 'c2' },
      { tenant_id: 't1', id: 'c3' },
      { tenant_id: null, id: 'c4' },
    ])
    expect(map.get('t1')?.map((c) => c.id)).toEqual(['c1', 'c3'])
    expect(map.get('t2')?.map((c) => c.id)).toEqual(['c2'])
  })
})
