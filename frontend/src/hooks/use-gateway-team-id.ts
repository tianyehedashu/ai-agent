/**
 * Gateway 路由 teamId 解析与工作区回退（personal team）。
 */

import { useMemo } from 'react'

import { useParams } from 'react-router-dom'

import { useGatewayTeamStore, type GatewayTeam } from '@/stores/gateway-team'

/** 稳定 primitive，供 queryKey / memo 使用（避免 selector 返回新数组） */
export function membershipTeamIdsKeyFromTeams(teams: readonly GatewayTeam[]): string {
  return teams.map((t) => t.id).join('|')
}

export function useGatewayMembershipTeamIdsKey(): string {
  return useGatewayTeamStore((s) => membershipTeamIdsKeyFromTeams(s.teams))
}

export function useGatewayMembershipTeamIds(): readonly string[] {
  const key = useGatewayMembershipTeamIdsKey()
  return useMemo(() => key.split('|').filter(Boolean), [key])
}

export function useGatewayMembershipTeamIdSet(): ReadonlySet<string> {
  const key = useGatewayMembershipTeamIdsKey()
  return useMemo(() => new Set(key.split('|').filter(Boolean)), [key])
}

export function useGatewayTeamId(): string {
  const { teamId } = useParams<{ teamId: string }>()
  if (!teamId) {
    throw new Error('Missing route param :teamId for Gateway team workspace')
  }
  return teamId
}

/** 可选 teamId（Guide 等无团队路由） */
export function useOptionalGatewayTeamId(): string | null {
  const { teamId } = useParams<{ teamId?: string }>()
  return teamId ?? null
}

/** 无 URL 团队段时的默认工作区：personal team */
export function useGatewayWorkspaceTeamId(): string | null {
  return useGatewayTeamStore((s) => {
    if (s.teams.length === 0) return null
    const personal = s.teams.find((t) => t.kind === 'personal')
    return personal?.id ?? s.teams[0].id
  })
}

/** 路由 teamId 优先，否则回退 personal 工作区（Guide / 侧栏导航等扁平路由） */
export function useResolvedGatewayTeamId(): string | null {
  const routeTeamId = useOptionalGatewayTeamId()
  const workspaceTeamId = useGatewayWorkspaceTeamId()
  return routeTeamId ?? workspaceTeamId
}

/** 从 store 缓存解析指定 teamId 的记录（须与路由 teamId 成对使用） */
export function useGatewayTeamRecord(teamId: string | null): GatewayTeam | null {
  return useGatewayTeamStore((s) =>
    teamId ? (s.teams.find((t) => t.id === teamId) ?? null) : null
  )
}
