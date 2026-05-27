/**
 * 团队管理页：解析 URL teamId 与删除/退出后的协作团队回退。
 */

import type { GatewayTeam } from '@/api/gateway/teams'

import { filterCollaborationGatewayTeams } from './gateway-team-collaboration'

/** 当前 teamId 不在协作团队列表中时，返回应重定向到的首个 shared team id */
export function resolveMembersPageTeamId(
  currentTeamId: string,
  teams: readonly GatewayTeam[]
): string | null {
  const collaborationTeams = filterCollaborationGatewayTeams(teams)
  if (collaborationTeams.length === 0) return null
  if (collaborationTeams.some((team) => team.id === currentTeamId)) return null
  return collaborationTeams[0]?.id ?? null
}

/** 删除/退出团队后，在剩余团队中选取首个 shared team id */
export function resolveMembersPageFallbackTeamId(teams: readonly GatewayTeam[]): string | null {
  const collaborationTeams = filterCollaborationGatewayTeams(teams)
  return collaborationTeams[0]?.id ?? null
}
