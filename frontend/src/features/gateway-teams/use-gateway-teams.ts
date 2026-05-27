/**
 * Gateway 团队列表（React Query 去重 + 标签 Map）
 */

import { useMemo } from 'react'

import { useQuery } from '@tanstack/react-query'

import { teamsApi, type GatewayTeam } from '@/api/gateway/teams'
import { filterCollaborationGatewayTeams } from '@/features/gateway-teams/gateway-team-collaboration'
import { gatewayTeamDisplayLabel } from '@/features/gateway-teams/gateway-team-display'
import { filterGatewayWritableTeams } from '@/features/gateway-teams/gateway-team-write-policy'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useUserStore } from '@/stores/user'

import type { UseQueryResult } from '@tanstack/react-query'

export const GATEWAY_TEAMS_QUERY_KEY = ['gateway', 'teams'] as const
export const GATEWAY_MEMBER_TEAMS_QUERY_KEY = ['gateway', 'teams', 'membership'] as const
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

/** membership 团队列表（平台 admin 不拉全站 personal team） */
export function useGatewayMemberTeams(enabled = true): UseQueryResult<GatewayTeam[]> {
  return useQuery({
    queryKey: GATEWAY_MEMBER_TEAMS_QUERY_KEY,
    queryFn: () => teamsApi.listTeams({ membership_only: true }),
    enabled,
    staleTime: GATEWAY_TEAMS_STALE_MS,
  })
}

export function useGatewayTeamNameMap(enabled = true): Map<string, string> {
  const { data: teams = [] } = useGatewayTeams(enabled)
  const viewerUserId = useUserStore((s) => s.currentUser?.id ?? null)

  return useMemo(() => {
    const map = new Map<string, string>()
    for (const team of teams) {
      map.set(team.id, gatewayTeamDisplayLabel(team, { viewerUserId }))
    }
    return map
  }, [teams, viewerUserId])
}

/** 侧栏 / Playground 团队选择器同源（membership_only） */
export function useGatewayMemberTeamNameMap(enabled = true): Map<string, string> {
  const { data: teams = [] } = useGatewayMemberTeams(enabled)
  const viewerUserId = useUserStore((s) => s.currentUser?.id ?? null)

  return useMemo(() => {
    const map = new Map<string, string>()
    for (const team of teams) {
      map.set(team.id, gatewayTeamDisplayLabel(team, { viewerUserId }))
    }
    return map
  }, [teams, viewerUserId])
}

export function useGatewayWritableTeams(enabled = true): GatewayTeam[] {
  const { data: teams = [] } = useGatewayTeams(enabled)
  const { isPlatformAdmin } = useGatewayPermission()

  return useMemo(() => filterGatewayWritableTeams(teams, isPlatformAdmin), [teams, isPlatformAdmin])
}

/** 跨团队汇总等管理面：membership 团队 + 可写过滤（对齐后端 list_gateway_team_memberships） */
export function useGatewayWritableMemberTeams(enabled = true): GatewayTeam[] {
  const { data: teams = [] } = useGatewayMemberTeams(enabled)
  const { isPlatformAdmin } = useGatewayPermission()

  return useMemo(() => filterGatewayWritableTeams(teams, isPlatformAdmin), [teams, isPlatformAdmin])
}

/** 团队凭据 Tab：可写协作团队（排除 personal team） */
export function useGatewayWritableCollaborationTeams(enabled = true): GatewayTeam[] {
  const writable = useGatewayWritableMemberTeams(enabled)
  return useMemo(() => filterCollaborationGatewayTeams(writable), [writable])
}

/** 平台 admin 跨团队搜索：按团队名称拉取全站活跃团队（需非空 search） */
export function useGatewayTeamsBySearch(search: string, enabled: boolean): GatewayTeam[] {
  const trimmedSearch = search.trim()
  const { data: teams = [] } = useQuery({
    queryKey: [...GATEWAY_TEAMS_QUERY_KEY, 'search', trimmedSearch] as const,
    queryFn: () => teamsApi.listTeams({ search: trimmedSearch }),
    enabled: enabled && trimmedSearch.length > 0,
    staleTime: GATEWAY_TEAMS_STALE_MS,
  })
  return teams
}

export function resolveGatewayTeamLabel(teamNameById: Map<string, string>, teamId: string): string {
  return teamNameById.get(teamId) ?? teamId.slice(0, 8)
}
