/**
 * Gateway 团队列表（React Query 去重 + 标签 Map）
 */

import { useMemo } from 'react'

import { useQuery } from '@tanstack/react-query'

import { teamsApi, type GatewayTeam } from '@/api/gateway/teams'
import { gatewayTeamDisplayLabel } from '@/features/gateway-teams/gateway-team-display'
import { filterGatewayWritableTeams } from '@/features/gateway-teams/gateway-team-write-policy'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'

import type { UseQueryResult } from '@tanstack/react-query'

export const GATEWAY_TEAMS_QUERY_KEY = ['gateway', 'teams'] as const
export const GATEWAY_TEAMS_STALE_MS = 60_000

export { gatewayTeamDisplayLabel }

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
      map.set(team.id, gatewayTeamDisplayLabel(team))
    }
    return map
  }, [teams])
}

export function useGatewayWritableTeams(enabled = true): GatewayTeam[] {
  const { data: teams = [] } = useGatewayTeams(enabled)
  const { isPlatformAdmin } = useGatewayPermission()

  return useMemo(() => filterGatewayWritableTeams(teams, isPlatformAdmin), [teams, isPlatformAdmin])
}

export function resolveGatewayTeamLabel(teamNameById: Map<string, string>, teamId: string): string {
  return teamNameById.get(teamId) ?? teamId.slice(0, 8)
}
