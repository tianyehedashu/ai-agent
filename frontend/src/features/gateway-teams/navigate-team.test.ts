import { beforeEach, describe, expect, it, vi } from 'vitest'

import { gatewayTeamPathSuffix, switchGatewayTeam, switchToFallbackTeam } from './navigate-team'

import type { QueryClient } from '@tanstack/react-query'

describe('gatewayTeamPathSuffix', () => {
  it('returns subpath for team workspace routes', () => {
    expect(gatewayTeamPathSuffix('/gateway/teams/t1/stats')).toBe('/stats')
    expect(gatewayTeamPathSuffix('/gateway/teams/t1/members')).toBe('/members')
  })

  it('defaults to /overview when only team root', () => {
    expect(gatewayTeamPathSuffix('/gateway/teams/t1')).toBe('/overview')
  })

  it('defaults to /overview on non-team paths', () => {
    expect(gatewayTeamPathSuffix('/gateway/guide')).toBe('/overview')
  })
})

describe('switchGatewayTeam', () => {
  const navigate = vi.fn()
  const invalidateQueries = vi.fn().mockResolvedValue(undefined)
  const queryClient = { invalidateQueries } as unknown as QueryClient

  beforeEach(() => {
    navigate.mockClear()
    invalidateQueries.mockClear()
  })

  it('navigates on team workspace routes preserving suffix', () => {
    switchGatewayTeam(
      'team-b',
      navigate,
      {
        pathname: '/gateway/teams/team-a/stats',
        search: '',
        hash: '',
        state: null,
        key: 'default',
      },
      queryClient
    )
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ['gateway'] })
    expect(navigate).toHaveBeenCalledWith('/gateway/teams/team-b/stats')
  })

  it('navigates to overview from flat routes', () => {
    switchGatewayTeam(
      'team-b',
      navigate,
      { pathname: '/gateway/guide', search: '', hash: '', state: null, key: 'default' },
      queryClient
    )
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ['gateway'] })
    expect(navigate).toHaveBeenCalledWith('/gateway/teams/team-b/overview')
  })
})

describe('switchToFallbackTeam', () => {
  const navigate = vi.fn()
  const queryClient = {
    invalidateQueries: vi.fn().mockResolvedValue(undefined),
  } as unknown as QueryClient

  beforeEach(() => {
    navigate.mockClear()
  })

  it('navigates to guide when no teams', () => {
    switchToFallbackTeam(
      [],
      navigate,
      { pathname: '/gateway', search: '', hash: '', state: null, key: 'default' },
      queryClient
    )
    expect(navigate).toHaveBeenCalledWith('/gateway/guide')
  })

  it('prefers personal team as fallback', () => {
    switchToFallbackTeam(
      [
        { id: 'shared-1', kind: 'shared' },
        { id: 'personal-1', kind: 'personal' },
      ],
      navigate,
      {
        pathname: '/gateway/teams/old/overview',
        search: '',
        hash: '',
        state: null,
        key: 'default',
      },
      queryClient
    )
    expect(navigate).toHaveBeenCalledWith('/gateway/teams/personal-1/overview')
  })
})
