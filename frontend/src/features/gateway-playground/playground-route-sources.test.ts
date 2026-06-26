import { describe, expect, it } from 'vitest'

import type { GatewayRoute, SharedRoute } from '@/api/gateway/routes'

import {
  mergePlaygroundRouteRows,
  resolvePlaygroundRouteFetchPolicy,
  sharedRouteToPlaygroundRow,
} from './playground-route-sources'

describe('resolvePlaygroundRouteFetchPolicy', () => {
  it('loads shared routes for shared team even when proxy model list is active', () => {
    expect(
      resolvePlaygroundRouteFetchPolicy({
        fetchRoutes: true,
        proxyTeamId: 'team-shared',
        isPersonalProxyTeam: false,
        credentialId: '',
        isPersonalCredential: false,
        usingProxyModelList: true,
      })
    ).toEqual({
      includeOwnedRoutes: false,
      includeSharedRoutes: true,
    })
  })

  it('skips shared routes on personal workspace', () => {
    expect(
      resolvePlaygroundRouteFetchPolicy({
        fetchRoutes: true,
        proxyTeamId: 'team-personal',
        isPersonalProxyTeam: true,
        credentialId: '',
        isPersonalCredential: false,
        usingProxyModelList: false,
      }).includeSharedRoutes
    ).toBe(false)
  })

  it('blocks all routes when personal credential filter is active', () => {
    expect(
      resolvePlaygroundRouteFetchPolicy({
        fetchRoutes: true,
        proxyTeamId: 'team-shared',
        isPersonalProxyTeam: false,
        credentialId: 'cred-user',
        isPersonalCredential: true,
        usingProxyModelList: false,
      })
    ).toEqual({
      includeOwnedRoutes: false,
      includeSharedRoutes: false,
    })
  })
})

describe('mergePlaygroundRouteRows', () => {
  const owned: GatewayRoute = {
    id: 'r1',
    team_id: 'team-a',
    virtual_model: 'team-route',
    primary_models: ['m1'],
    fallbacks_general: [],
    fallbacks_content_policy: [],
    fallbacks_context_window: [],
    strategy: 'simple-shuffle',
    enabled: true,
  }

  const shared: SharedRoute = {
    grant_id: 'g1',
    route_id: 'r2',
    tenant_id: 'team-a',
    exposed_alias: 'shared-alias',
    primary_models: ['m2'],
    enabled: true,
    created_at: '2026-01-01T00:00:00Z',
    owner_display: 'Alice',
  }

  it('merges owned and shared routes', () => {
    const merged = mergePlaygroundRouteRows([owned], [shared])
    expect(merged.map((row) => row.virtual_model)).toEqual(['team-route', 'shared-alias'])
    expect(merged[1]?.isSharedRoute).toBe(true)
    expect(merged[1]?.ownerDisplay).toBe('Alice')
  })

  it('prefers owned route when alias collides with exposed_alias', () => {
    const collisionShared: SharedRoute = {
      ...shared,
      exposed_alias: 'team-route',
    }
    const merged = mergePlaygroundRouteRows([owned], [collisionShared])
    expect(merged).toHaveLength(1)
    expect(merged[0]?.isSharedRoute).toBe(false)
  })
})

describe('sharedRouteToPlaygroundRow', () => {
  it('maps exposed_alias to virtual_model', () => {
    const row = sharedRouteToPlaygroundRow({
      grant_id: 'g1',
      route_id: 'r1',
      tenant_id: 'team-a',
      exposed_alias: 'alias-x',
      primary_models: ['m-a'],
      enabled: true,
      created_at: '2026-01-01T00:00:00Z',
    })
    expect(row).toMatchObject({
      virtual_model: 'alias-x',
      primary_models: ['m-a'],
      enabled: true,
      isSharedRoute: true,
    })
  })
})
