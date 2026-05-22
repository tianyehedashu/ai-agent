/**
 * Gateway 团队列表（React Query 去重 + 标签 Map）
 */

import { useMemo } from 'react'

import { useQuery } from '@tanstack/react-query'

import { teamsApi, type GatewayTeam } from '@/api/gateway/teams'

import type { UseQueryResult } from '@tanstack/react-query'

export const GATEWAY_TEAMS_QUERY_KEY = ['gateway', 'teams'] as const
export const GATEWAY_TEAMS_STALE_MS = 60_000

export function useGatewayTeams(enabled = true): UseQueryResult<GatewayTeam[]> {
  return useQuery({
    queryKey: GATEWAY_TEAMS_QUERY_KEY,
    queryFn: () => teamsApi.listTeams(),
    enabled,
    staleTime: GATEWAY_TEAMS_STALE_MS,
  })
}

export function useGatewayTeamNameMap(enabled = true): Map<string, string> {
  const { data: teams = [] } = useGatewayTeams(enabled)

  return useMemo(() => {
    const map = new Map<string, string>()
    for (const team of teams) {
      map.set(team.id, team.kind === 'personal' ? '个人工作区' : team.name)
    }
    return map
  }, [teams])
}

export function resolveGatewayTeamLabel(teamNameById: Map<string, string>, teamId: string): string {
  return teamNameById.get(teamId) ?? teamId.slice(0, 8)
}
