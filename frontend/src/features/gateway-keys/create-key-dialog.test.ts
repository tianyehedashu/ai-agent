import { describe, expect, it } from 'vitest'

import type { GatewayTeam } from '@/api/gateway/teams'
import { grantableCrossTeams } from '@/features/gateway-keys/create-key-dialog'

const TEAMS: GatewayTeam[] = [
  {
    id: 'personal-1',
    name: '个人工作区',
    slug: 'user-a',
    kind: 'personal',
    owner_user_id: 'u1',
  },
  {
    id: 'shared-1',
    name: '协作 A',
    slug: 'team-a',
    kind: 'shared',
    owner_user_id: 'u1',
  },
  {
    id: 'shared-2',
    name: '协作 B',
    slug: 'team-b',
    kind: 'shared',
    owner_user_id: 'u1',
  },
]

describe('grantableCrossTeams', () => {
  it('excludes bound team from cross-grant candidates', () => {
    expect(grantableCrossTeams(TEAMS, 'personal-1').map((t) => t.id)).toEqual([
      'shared-1',
      'shared-2',
    ])
  })

  it('returns empty when only one membership team', () => {
    expect(grantableCrossTeams([TEAMS[0]], 'personal-1')).toEqual([])
  })
})
