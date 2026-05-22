import { renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const useParamsMock = vi.fn<[], Record<string, string | undefined>>()

vi.mock('react-router-dom', () => ({
  useParams: () => useParamsMock(),
}))

import { useGatewayTeamStore } from '@/stores/gateway-team'

import {
  useGatewayTeamId,
  useOptionalGatewayTeamId,
  useResolvedGatewayTeamId,
} from './use-gateway-team-id'

describe('useGatewayTeamId', () => {
  beforeEach(() => {
    useParamsMock.mockReturnValue({})
    useGatewayTeamStore.setState({ teams: [], currentTeamId: null })
  })

  it('throws when route param missing', () => {
    expect(() => renderHook(() => useGatewayTeamId())).toThrow(
      /Missing route param :teamId for Gateway team workspace/
    )
  })

  it('returns route teamId and syncs store', () => {
    useParamsMock.mockReturnValue({ teamId: 'team-route' })
    const { result } = renderHook(() => useGatewayTeamId())
    expect(result.current).toBe('team-route')
    expect(useGatewayTeamStore.getState().currentTeamId).toBe('team-route')
  })
})

describe('useOptionalGatewayTeamId', () => {
  beforeEach(() => {
    useParamsMock.mockReturnValue({})
    useGatewayTeamStore.setState({ teams: [], currentTeamId: null })
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
    useGatewayTeamStore.setState({ teams: [], currentTeamId: null })
  })

  it('prefers route param over store', () => {
    useParamsMock.mockReturnValue({ teamId: 'team-route' })
    useGatewayTeamStore.setState({ currentTeamId: 'team-store' })
    const { result } = renderHook(() => useResolvedGatewayTeamId())
    expect(result.current).toBe('team-route')
  })

  it('falls back to store on Guide-like flat routes', () => {
    useGatewayTeamStore.setState({ currentTeamId: 'team-store' })
    const { result } = renderHook(() => useResolvedGatewayTeamId())
    expect(result.current).toBe('team-store')
  })

  it('returns null when neither route nor store has teamId', () => {
    const { result } = renderHook(() => useResolvedGatewayTeamId())
    expect(result.current).toBeNull()
  })
})
