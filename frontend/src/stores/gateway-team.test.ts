import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { useGatewayTeamStore } from '@/stores/gateway-team'

const STORAGE_KEY = 'gateway-team-storage'

describe('gateway-team store', () => {
  beforeEach(() => {
    localStorage.removeItem(STORAGE_KEY)
    useGatewayTeamStore.setState({ teams: [], currentTeamId: null })
  })

  afterEach(() => {
    localStorage.removeItem(STORAGE_KEY)
  })

  it('setTeams 保留仍存在于列表中的 currentTeamId', () => {
    useGatewayTeamStore.getState().setCurrentTeamId('team-a')
    useGatewayTeamStore.getState().setTeams([
      { id: 'team-a', name: 'A', slug: 'a', kind: 'shared' },
      { id: 'team-p', name: 'P', slug: 'p', kind: 'personal' },
    ])
    expect(useGatewayTeamStore.getState().currentTeamId).toBe('team-a')
  })

  it('setTeams 在 current 不在列表时回退到 personal team', () => {
    useGatewayTeamStore.getState().setCurrentTeamId('missing')
    useGatewayTeamStore.getState().setTeams([
      { id: 'team-p', name: 'P', slug: 'p', kind: 'personal' },
      { id: 'team-s', name: 'S', slug: 's', kind: 'shared' },
    ])
    expect(useGatewayTeamStore.getState().currentTeamId).toBe('team-p')
  })

  it('setTeams 无 personal 时回退到第一个团队', () => {
    useGatewayTeamStore.getState().setCurrentTeamId('missing')
    useGatewayTeamStore.getState().setTeams([{ id: 'first', name: 'F', slug: 'f', kind: 'shared' }])
    expect(useGatewayTeamStore.getState().currentTeamId).toBe('first')
  })
})
