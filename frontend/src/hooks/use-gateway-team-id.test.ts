import { renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const useParamsMock = vi.fn<[], Record<string, string | undefined>>()

vi.mock('react-router-dom', () => ({
  useParams: () => useParamsMock(),
}))

import { useGatewayTeamStore } from '@/stores/gateway-team'

import {
  useGatewayTeamId,
  useGatewayTeamRecord,
  useOptionalGatewayTeamId,
  useResolvedGatewayTeamId,
} from './use-gateway-team-id'

describe('useGatewayTeamId', () => {
  beforeEach(() => {
    useParamsMock.mockReturnValue({})
    useGatewayTeamStore.setState({ teams: [] })
  })

  it('throws when route param missing', () => {
    expect(() => renderHook(() => useGatewayTeamId())).toThrow(
      /Missing route param :teamId for Gateway team workspace/
    )
  })

  it('returns route teamId', () => {
    useParamsMock.mockReturnValue({ teamId: 'team-route' })
    const { result } = renderHook(() => useGatewayTeamId())
    expect(result.current).toBe('team-route')
  })
})

describe('useOptionalGatewayTeamId', () => {
  beforeEach(() => {
    useParamsMock.mockReturnValue({})
    useGatewayTeamStore.setState({ teams: [] })
  })

  it('returns null on flat routes', () => {
    const { result } = renderHook(() => useOptionalGatewayTeamId())
    expect(result.current).toBeNull()
  })

  it('returns route teamId when present', () => {
    useParamsMock.mockReturnValue({ teamId: 'team-a' })
    const { result } = renderHook(() => useOptionalGatewayTeamId())
    expect(result.current).toBe('team-a')
  })
})

describe('useResolvedGatewayTeamId', () => {
  beforeEach(() => {
    useParamsMock.mockReturnValue({})
    useGatewayTeamStore.setState({ teams: [] })
  })

  it('prefers route param over workspace team', () => {
    useParamsMock.mockReturnValue({ teamId: 'team-route' })
    useGatewayTeamStore.setState({
      teams: [
        {
          id: 'team-personal',
          name: 'Personal',
          slug: 'personal',
          kind: 'personal',
        },
      ],
    })
    const { result } = renderHook(() => useResolvedGatewayTeamId())
    expect(result.current).toBe('team-route')
  })

  it('falls back to personal workspace team on flat routes', () => {
    useGatewayTeamStore.setState({
      teams: [
        {
          id: 'team-personal',
          name: 'Personal',
          slug: 'personal',
          kind: 'personal',
        },
        {
          id: 'team-shared',
          name: '研发',
          slug: 'dev',
          kind: 'shared',
        },
      ],
    })
    const { result } = renderHook(() => useResolvedGatewayTeamId())
    expect(result.current).toBe('team-personal')
  })

  it('returns null when neither route nor teams cache has teamId', () => {
    const { result } = renderHook(() => useResolvedGatewayTeamId())
    expect(result.current).toBeNull()
  })
})

describe('useGatewayTeamRecord', () => {
  beforeEach(() => {
    useGatewayTeamStore.setState({
      teams: [{ id: 'team-a', name: 'A', slug: 'a', kind: 'shared' }],
    })
  })

  it('returns team record for id', () => {
    const { result } = renderHook(() => useGatewayTeamRecord('team-a'))
    expect(result.current?.name).toBe('A')
  })

  it('returns null for unknown id', () => {
    const { result } = renderHook(() => useGatewayTeamRecord('missing'))
    expect(result.current).toBeNull()
  })
})
