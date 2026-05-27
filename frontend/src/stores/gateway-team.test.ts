import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { useGatewayTeamStore } from '@/stores/gateway-team'

const STORAGE_KEY = 'gateway-team-storage'

describe('gateway-team store', () => {
  beforeEach(() => {
    localStorage.removeItem(STORAGE_KEY)
    useGatewayTeamStore.setState({ teams: [] })
  })

  afterEach(() => {
    localStorage.removeItem(STORAGE_KEY)
  })

  it('setTeams replaces membership cache', () => {
    useGatewayTeamStore.getState().setTeams([
      { id: 'team-a', name: 'A', slug: 'a', kind: 'shared' },
      { id: 'team-p', name: 'P', slug: 'p', kind: 'personal' },
    ])
    expect(useGatewayTeamStore.getState().teams.map((t) => t.id)).toEqual(['team-a', 'team-p'])
  })

  it('clear resets teams', () => {
    useGatewayTeamStore
      .getState()
      .setTeams([{ id: 'team-a', name: 'A', slug: 'a', kind: 'shared' }])
    useGatewayTeamStore.getState().clear()
    expect(useGatewayTeamStore.getState().teams).toEqual([])
  })
})
