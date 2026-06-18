/**
 * Gateway 团队列表（React Query 去重 + 标签 Map）
 */

import { useMemo } from 'react'

import { useQuery } from '@tanstack/react-query'

import { teamsApi, type GatewayTeam } from '@/api/gateway/teams'
import { filterCollaborationGatewayTeams } from '@/features/gateway-teams/gateway-team-collaboration'
import {
  gatewayTeamDisplayLabel,
  gatewayWorkspaceLabel,
} from '@/features/gateway-teams/gateway-team-display'
import {
  filterGatewayContributorTeams,
  filterGatewayWritableTeams,
} from '@/features/gateway-teams/gateway-team-write-policy'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useCurrentUser } from '@/stores/user'

import type { UseQueryResult } from '@tanstack/react-query'

export const GATEWAY_TEAMS_QUERY_KEY = ['gateway', 'teams'] as const
export const GATEWAY_MEMBER_TEAMS_QUERY_KEY = ['gateway', 'teams', 'membership'] as const
export const GATEWAY_TEAMS_STALE_MS = 60_000

export { gatewayTeamDisplayLabel, gatewayWorkspaceLabel }

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
  const viewerUserId = useCurrentUser()?.id ?? null

  return useMemo(() => {
    const map = new Map<string, string>()
    for (const team of teams) {
      map.set(team.id, gatewayTeamDisplayLabel(team, { viewerUserId }))
    }
    return map
  }, [teams, viewerUserId])
}

/** Playground / 团队管理页等同源（membership_only） */
export function useGatewayMemberTeamNameMap(enabled = true): Map<string, string> {
  const { data: teams = [] } = useGatewayMemberTeams(enabled)
  const viewerUserId = useCurrentUser()?.id ?? null

  return useMemo(() => {
    const map = new Map<string, string>()
    for (const team of teams) {
      map.set(team.id, gatewayTeamDisplayLabel(team, { viewerUserId }))
    }
    return map
  }, [teams, viewerUserId])
}

/** 虚拟 Key 等工作区列：本人 personal 显示「个人」 */
export function useGatewayMemberWorkspaceNameMap(enabled = true): Map<string, string> {
  const { data: teams = [] } = useGatewayMemberTeams(enabled)
  const viewerUserId = useCurrentUser()?.id ?? null

  return useMemo(() => {
    const map = new Map<string, string>()
    for (const team of teams) {
      map.set(team.id, gatewayWorkspaceLabel(team, { viewerUserId }))
    }
    return map
  }, [teams, viewerUserId])
}

export function useGatewayWritableTeams(enabled = true): GatewayTeam[] {
  const { data: teams = [] } = useGatewayTeams(enabled)
  const { isPlatformAdmin, isPlatformViewer } = useGatewayPermission()

  return useMemo(
    () => filterGatewayWritableTeams(teams, isPlatformAdmin, isPlatformViewer),
    [teams, isPlatformAdmin, isPlatformViewer]
  )
}

/** 跨团队汇总等管理面：membership 团队 + 可写过滤（对齐后端 list_gateway_team_memberships） */
export function useGatewayWritableMemberTeams(enabled = true): GatewayTeam[] {
  const { data: teams = [] } = useGatewayMemberTeams(enabled)
  const { isPlatformAdmin, isPlatformViewer } = useGatewayPermission()

  return useMemo(
    () => filterGatewayWritableTeams(teams, isPlatformAdmin, isPlatformViewer),
    [teams, isPlatformAdmin, isPlatformViewer]
  )
}

/** 虚拟 Key 创建绑定工作区：membership 内全部团队（member+ 可建，对齐后端 RequiredTeamMember） */
export function useGatewayVkeyTargetTeams(enabled = true): GatewayTeam[] {
  const { data: teams = [] } = useGatewayMemberTeams(enabled)
  return teams
}

/** 团队凭据 Tab：可写协作团队（排除 personal team） */
export function useGatewayWritableCollaborationTeams(enabled = true): GatewayTeam[] {
  const writable = useGatewayWritableMemberTeams(enabled)
  return useMemo(() => filterCollaborationGatewayTeams(writable), [writable])
}

/** 团队凭据/模型 Tab：membership 内全部协作团队（member 只读 + admin 可写） */
export function useGatewayMemberCollaborationTeams(enabled = true): GatewayTeam[] {
  const { data: teams = [] } = useGatewayMemberTeams(enabled)
  return useMemo(() => filterCollaborationGatewayTeams(teams), [teams])
}

/**
 * 可创建团队凭据的协作团队：membership 协作团队 + 贡献者过滤（member+，排除平台 viewer）。
 * 对齐后端 `POST /teams/{id}/credentials`（member+）；凭据创建后归创建者私有。
 */
export function useGatewayContributorCollaborationTeams(enabled = true): GatewayTeam[] {
  const { data: teams = [] } = useGatewayMemberTeams(enabled)
  const { isPlatformAdmin, isPlatformViewer } = useGatewayPermission()
  return useMemo(
    () =>
      filterCollaborationGatewayTeams(
        filterGatewayContributorTeams(teams, isPlatformAdmin, isPlatformViewer)
      ),
    [teams, isPlatformAdmin, isPlatformViewer]
  )
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

export function resolveGatewayTeamLabel(
  teamNameById: ReadonlyMap<string, string>,
  teamId: string
): string {
  return teamNameById.get(teamId) ?? teamId.slice(0, 8)
}
