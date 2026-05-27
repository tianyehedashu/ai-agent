/**
 * 分组列表：解析可展示的协作团队候选（凭据/模型共用）。
 */

import type { GatewayTeam } from '@/api/gateway/teams'
import { filterCollaborationGatewayTeams } from '@/features/gateway-teams/gateway-team-collaboration'
import { gatewayTeamDisplayLabel } from '@/features/gateway-teams/gateway-team-display'
import { filterGatewayWritableTeams } from '@/features/gateway-teams/gateway-team-write-policy'

import { filterWritableTeamsBySearch } from './filter-writable-teams-by-search'

/** 平台 admin 无搜索时不渲染全站团队列表的阈值 */
export const COLLABORATION_TEAMS_REQUIRE_SEARCH_THRESHOLD = 50

export interface ResolveCollaborationTeamsCandidatesInput {
  isPlatformAdmin: boolean
  hasSearch: boolean
  queriedTeamCount: number
  candidateTeams: readonly GatewayTeam[]
  search: string
  viewerUserId?: string | null
}

export interface ResolveCollaborationTeamsCandidatesResult {
  teams: GatewayTeam[]
  requiresSearch: boolean
}

function sortTeamsByDisplayLabel(
  teams: GatewayTeam[],
  viewerUserId?: string | null
): GatewayTeam[] {
  return [...teams].sort((a, b) => {
    const la = gatewayTeamDisplayLabel(a, { viewerUserId })
    const lb = gatewayTeamDisplayLabel(b, { viewerUserId })
    return la.localeCompare(lb, 'zh-CN')
  })
}

export function resolveCollaborationTeamsCandidates({
  isPlatformAdmin,
  hasSearch,
  queriedTeamCount,
  candidateTeams,
  search,
  viewerUserId,
}: ResolveCollaborationTeamsCandidatesInput): ResolveCollaborationTeamsCandidatesResult {
  if (
    isPlatformAdmin &&
    !hasSearch &&
    queriedTeamCount > COLLABORATION_TEAMS_REQUIRE_SEARCH_THRESHOLD
  ) {
    return { teams: [], requiresSearch: true }
  }

  const writableCandidates = filterGatewayWritableTeams([...candidateTeams], isPlatformAdmin)
  const collaborationCandidates = filterCollaborationGatewayTeams(writableCandidates)
  const filtered = filterWritableTeamsBySearch(collaborationCandidates, search, viewerUserId)

  return {
    teams: sortTeamsByDisplayLabel(filtered, viewerUserId),
    requiresSearch: false,
  }
}

export function groupResourcesByTenantId<
  T extends { tenant_id?: string | null; team_id?: string | null },
>(
  items: readonly T[],
  resolveTenantId: (item: T) => string | null = (item) => item.tenant_id ?? item.team_id ?? null
): Map<string, T[]> {
  const map = new Map<string, T[]>()
  for (const item of items) {
    const tenantId = resolveTenantId(item)
    if (!tenantId) continue
    const list = map.get(tenantId) ?? []
    list.push(item)
    map.set(tenantId, list)
  }
  return map
}
