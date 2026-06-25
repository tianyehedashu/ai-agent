import { describe, expect, it } from 'vitest'

import type { GatewayRoute } from '@/api/gateway/routes'
import type { GatewayTeam } from '@/api/gateway/teams'

import {
  isForeignPersonalRouteView,
  isPersonalRouteRecord,
  resolveSelectedRouteEditable,
  resolveUsePersonalCallableModels,
} from './route-workspace-policy'

const myPersonalTeamId = 'personal-me'
const otherPersonalTeamId = 'personal-other'
const sharedTeamId = 'shared-team'

const memberTeams: GatewayTeam[] = [
  {
    id: myPersonalTeamId,
    name: '我',
    slug: 'personal-me',
    kind: 'personal',
    owner_user_id: 'user-me',
    team_role: 'owner',
  },
  {
    id: sharedTeamId,
    name: '研发API',
    slug: 'team-api',
    kind: 'shared',
    owner_user_id: 'user-other',
    team_role: 'member',
  },
]

function route(
  partial: Partial<GatewayRoute> & Pick<GatewayRoute, 'id' | 'virtual_model'>
): GatewayRoute {
  return {
    team_id: myPersonalTeamId,
    primary_models: [],
    fallbacks_general: [],
    fallbacks_content_policy: [],
    fallbacks_context_window: [],
    strategy: 'simple-shuffle',
    enabled: true,
    ...partial,
  }
}

describe('isPersonalRouteRecord', () => {
  it('marks aggregated personal route as personal record', () => {
    expect(
      isPersonalRouteRecord({
        createMode: false,
        selectedRoute: route({
          id: 'r1',
          virtual_model: 'volcano-pool',
          team_id: otherPersonalTeamId,
          owner_team_kind: 'personal',
        }),
        activeTeamId: otherPersonalTeamId,
        memberTeams,
      })
    ).toBe(true)
  })
})

describe('resolveUsePersonalCallableModels', () => {
  it('does not use viewer callable list for another users personal route', () => {
    expect(
      resolveUsePersonalCallableModels({
        createMode: false,
        selectedRoute: route({
          id: 'r1',
          virtual_model: 'volcano-pool',
          team_id: otherPersonalTeamId,
          owner_team_kind: 'personal',
        }),
        activeTeamId: otherPersonalTeamId,
        memberTeams,
      })
    ).toBe(false)
  })

  it('uses callable list for own personal route', () => {
    expect(
      resolveUsePersonalCallableModels({
        createMode: false,
        selectedRoute: route({
          id: 'r4',
          virtual_model: 'my-route',
          team_id: myPersonalTeamId,
          owner_team_kind: 'personal',
        }),
        activeTeamId: myPersonalTeamId,
        memberTeams,
      })
    ).toBe(true)
  })

  it('falls back to memberTeams when owner_team_kind is absent', () => {
    expect(
      resolveUsePersonalCallableModels({
        createMode: false,
        selectedRoute: route({
          id: 'r2',
          virtual_model: 'team-route',
          team_id: sharedTeamId,
        }),
        activeTeamId: sharedTeamId,
        memberTeams,
      })
    ).toBe(false)
  })

  it('create mode still uses activeTeamId membership', () => {
    expect(
      resolveUsePersonalCallableModels({
        createMode: true,
        selectedRoute: null,
        activeTeamId: myPersonalTeamId,
        memberTeams,
      })
    ).toBe(true)
  })
})

describe('isForeignPersonalRouteView', () => {
  it('detects cross-account personal route view', () => {
    expect(
      isForeignPersonalRouteView({
        selectedRoute: route({
          id: 'r1',
          virtual_model: 'volcano-pool',
          team_id: otherPersonalTeamId,
          owner_team_kind: 'personal',
        }),
        memberTeams,
      })
    ).toBe(true)
  })

  it('returns false for own personal route', () => {
    expect(
      isForeignPersonalRouteView({
        selectedRoute: route({
          id: 'r4',
          virtual_model: 'my-route',
          team_id: myPersonalTeamId,
          owner_team_kind: 'personal',
        }),
        memberTeams,
      })
    ).toBe(false)
  })
})

describe('resolveSelectedRouteEditable', () => {
  it('platform admin cannot edit another users personal route', () => {
    expect(
      resolveSelectedRouteEditable({
        selectedRoute: route({
          id: 'r3',
          virtual_model: 'volcano-pool',
          team_id: otherPersonalTeamId,
          owner_team_kind: 'personal',
        }),
        memberTeams,
        isPlatformAdmin: true,
        isPlatformViewer: false,
      })
    ).toBe(false)
  })

  it('owner can edit own personal route', () => {
    expect(
      resolveSelectedRouteEditable({
        selectedRoute: route({
          id: 'r4',
          virtual_model: 'my-route',
          team_id: myPersonalTeamId,
          owner_team_kind: 'personal',
        }),
        memberTeams,
        isPlatformAdmin: false,
        isPlatformViewer: false,
      })
    ).toBe(true)
  })

  it('platform admin can still edit shared team routes', () => {
    expect(
      resolveSelectedRouteEditable({
        selectedRoute: route({
          id: 'r5',
          virtual_model: 'shared-route',
          team_id: sharedTeamId,
          owner_team_kind: 'shared',
        }),
        memberTeams,
        isPlatformAdmin: true,
        isPlatformViewer: false,
      })
    ).toBe(true)
  })
})
