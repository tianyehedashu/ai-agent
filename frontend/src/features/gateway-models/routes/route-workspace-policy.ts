/**
 * 虚拟路由工作区：个人/协作上下文与编辑权限（纯函数，供 route-workspace 与单测复用）。
 */

import type { GatewayRoute } from '@/api/gateway/routes'
import type { GatewayTeam } from '@/api/gateway/teams'
import { isGatewayTeamWritable } from '@/features/gateway-teams/gateway-team-write-policy'

import { resolveGatewayRouteTeamId } from './use-visible-gateway-routes'

export function isPersonalTeamId(teamId: string, memberTeams: readonly GatewayTeam[]): boolean {
  return memberTeams.some((team) => team.id === teamId && team.kind === 'personal')
}

export function canManageTeamRoutes(
  targetTeamId: string,
  memberTeams: readonly GatewayTeam[],
  isPlatformAdmin: boolean,
  isPlatformViewer: boolean
): boolean {
  if (isPlatformViewer) return false
  if (isPlatformAdmin) return true
  const team = memberTeams.find((item) => item.id === targetTeamId)
  return team ? isGatewayTeamWritable(team, false) : false
}

/** 路由记录是否归属个人团队（用于共享面板、批量添加等 UI 语义）。 */
export function isPersonalRouteRecord(params: {
  createMode: boolean
  selectedRoute: GatewayRoute | null
  activeTeamId: string
  memberTeams: readonly GatewayTeam[]
}): boolean {
  const { createMode, selectedRoute, activeTeamId, memberTeams } = params
  if (
    !createMode &&
    selectedRoute?.owner_team_kind !== undefined &&
    selectedRoute.owner_team_kind !== null
  ) {
    return selectedRoute.owner_team_kind === 'personal'
  }
  return isPersonalTeamId(activeTeamId, memberTeams)
}

/**
 * 是否应走个人路由 callable 模型列表（/my-route-callable-models）。
 * 仅当查看者本人拥有该 personal team 时为 true；跨账号只读查看他人个人路由时为 false。
 */
export function resolveUsePersonalCallableModels(params: {
  createMode: boolean
  selectedRoute: GatewayRoute | null
  activeTeamId: string
  memberTeams: readonly GatewayTeam[]
}): boolean {
  const { createMode, selectedRoute, activeTeamId, memberTeams } = params
  if (createMode) {
    return isPersonalTeamId(activeTeamId, memberTeams)
  }
  if (selectedRoute?.owner_team_kind === 'personal') {
    const ownerTeamId = resolveGatewayRouteTeamId(selectedRoute)
    if (!ownerTeamId) return false
    return isPersonalTeamId(ownerTeamId, memberTeams)
  }
  if (selectedRoute?.owner_team_kind === 'shared' || selectedRoute?.owner_team_kind === 'system') {
    return false
  }
  return isPersonalTeamId(activeTeamId, memberTeams)
}

/** 平台 admin 等跨账号只读查看他人个人路由（不拉取任何模型池）。 */
export function isForeignPersonalRouteView(params: {
  selectedRoute: GatewayRoute | null
  memberTeams: readonly GatewayTeam[]
}): boolean {
  const { selectedRoute, memberTeams } = params
  if (selectedRoute?.owner_team_kind !== 'personal') return false
  const ownerTeamId = resolveGatewayRouteTeamId(selectedRoute)
  if (!ownerTeamId) return false
  return !isPersonalTeamId(ownerTeamId, memberTeams)
}

/** 当前选中路由是否可编辑（含平台 admin 跨账号查看他人个人路由 → 只读）。 */
export function resolveSelectedRouteEditable(params: {
  selectedRoute: GatewayRoute | null
  memberTeams: readonly GatewayTeam[]
  isPlatformAdmin: boolean
  isPlatformViewer: boolean
}): boolean {
  const { selectedRoute, memberTeams, isPlatformAdmin, isPlatformViewer } = params
  if (selectedRoute === null || selectedRoute.source === 'system') return false
  const ownerTeamId = resolveGatewayRouteTeamId(selectedRoute)
  if (!ownerTeamId) return false
  if (selectedRoute.owner_team_kind === 'personal') {
    return isPersonalTeamId(ownerTeamId, memberTeams)
  }
  return canManageTeamRoutes(ownerTeamId, memberTeams, isPlatformAdmin, isPlatformViewer)
}
