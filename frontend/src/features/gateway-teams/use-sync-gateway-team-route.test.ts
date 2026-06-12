import { describe, expect, it } from 'vitest'

import { shouldRedirectInvalidGatewayTeamRoute } from './use-sync-gateway-team-route'

const MEMBERSHIP = new Set(['team-a', 'team-p'])

describe('shouldRedirectInvalidGatewayTeamRoute', () => {
  it('does not redirect while membership API is not ready', () => {
    expect(
      shouldRedirectInvalidGatewayTeamRoute({
        routeTeamId: 'team-b',
        teamsCount: 2,
        membershipTeamsReady: false,
        isPlatformAdmin: false,
        membershipTeamIds: MEMBERSHIP,
      })
    ).toBe(false)
  })

  it('does not redirect when route team is in membership', () => {
    expect(
      shouldRedirectInvalidGatewayTeamRoute({
        routeTeamId: 'team-a',
        teamsCount: 2,
        membershipTeamsReady: true,
        isPlatformAdmin: false,
        membershipTeamIds: MEMBERSHIP,
      })
    ).toBe(false)
  })

  it('redirects when route team is outside membership', () => {
    expect(
      shouldRedirectInvalidGatewayTeamRoute({
        routeTeamId: 'team-b',
        teamsCount: 2,
        membershipTeamsReady: true,
        isPlatformAdmin: false,
        membershipTeamIds: MEMBERSHIP,
      })
    ).toBe(true)
  })

  it('does not redirect for platform admin on non-membership team', () => {
    expect(
      shouldRedirectInvalidGatewayTeamRoute({
        routeTeamId: 'foreign-team',
        teamsCount: 2,
        membershipTeamsReady: true,
        isPlatformAdmin: true,
        membershipTeamIds: MEMBERSHIP,
      })
    ).toBe(false)
  })

  it('redirects when membership is empty', () => {
    expect(
      shouldRedirectInvalidGatewayTeamRoute({
        routeTeamId: 'team-a',
        teamsCount: 0,
        membershipTeamsReady: true,
        isPlatformAdmin: false,
        membershipTeamIds: new Set(),
      })
    ).toBe(true)
  })
})
