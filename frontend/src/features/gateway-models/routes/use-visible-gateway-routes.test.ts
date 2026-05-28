import { describe, expect, it } from 'vitest'

import type { GatewayRoute } from '@/api/gateway'

import { resolveGatewayRouteTeamId } from './use-visible-gateway-routes'

function route(
  partial: Partial<GatewayRoute> & Pick<GatewayRoute, 'id' | 'virtual_model'>
): GatewayRoute {
  return {
    team_id: 'team-1',
    primary_models: [],
    fallbacks_general: [],
    fallbacks_content_policy: [],
    fallbacks_context_window: [],
    strategy: 'simple-shuffle',
    enabled: true,
    ...partial,
  }
}

describe('resolveGatewayRouteTeamId', () => {
  it('prefers team_id then tenant_id', () => {
    expect(
      resolveGatewayRouteTeamId(
        route({ id: '1', virtual_model: 'a', team_id: 'team-a', tenant_id: 'team-b' })
      )
    ).toBe('team-a')
    expect(
      resolveGatewayRouteTeamId(
        route({ id: '2', virtual_model: 'b', team_id: null, tenant_id: 'team-c' })
      )
    ).toBe('team-c')
  })
})
