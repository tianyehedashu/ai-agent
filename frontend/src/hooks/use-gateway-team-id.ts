/**
 * Gateway 路由 teamId 解析与工作区回退（personal team）。
 */

import { useMemo } from 'react'

import { useParams } from 'react-router-dom'

import { useGatewayTeamStore, type GatewayTeam } from '@/stores/gateway-team'

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
  const teams = useGatewayTeamStore((s) => s.teams)
  return useMemo((): string | null => {
    const personal = teams.find((t) => t.kind === 'personal')
    if (personal) return personal.id
    return teams[0]?.id ?? null
  }, [teams])
}

/** 路由 teamId 优先，否则回退 personal 工作区（Guide / 侧栏导航等扁平路由） */
export function useResolvedGatewayTeamId(): string | null {
  const routeTeamId = useOptionalGatewayTeamId()
  const workspaceTeamId = useGatewayWorkspaceTeamId()
  return routeTeamId ?? workspaceTeamId
}

/** 从 store 缓存解析指定 teamId 的记录（须与路由 teamId 成对使用） */
export function useGatewayTeamRecord(teamId: string | null): GatewayTeam | null {
  const teams = useGatewayTeamStore((s) => s.teams)
  return useMemo(
    () => (teamId ? (teams.find((t) => t.id === teamId) ?? null) : null),
    [teams, teamId]
  )
}
