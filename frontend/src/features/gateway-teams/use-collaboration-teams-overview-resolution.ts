/**
 * 协作团队分组列表：团队候选解析（凭据/模型共用）。
 */

import { useDeferredValue, useMemo } from 'react'

import type { GatewayModel } from '@/api/gateway'
import type { GatewayTeam } from '@/api/gateway/teams'
import { filterCollaborationGatewayTeams } from '@/features/gateway-teams/gateway-team-collaboration'
import {
  COLLABORATION_TEAMS_REQUIRE_SEARCH_THRESHOLD,
  groupResourcesByTenantId,
  resolveCollaborationTeamsCandidates,
} from '@/features/gateway-teams/resolve-collaboration-teams-candidates'
import {
  useGatewayMemberCollaborationTeams,
  useGatewayTeams,
  useGatewayTeamsBySearch,
} from '@/features/gateway-teams/use-gateway-teams'

export interface UseCollaborationTeamsOverviewResolutionOptions {
  teamSearch: string
  queriedTeamCount: number | undefined
  isPlatformAdmin: boolean
  viewerUserId?: string | null
  enabled: boolean
}

export interface CollaborationTeamsOverviewResolution {
  teams: GatewayTeam[]
  requiresSearch: boolean
  isSearchStale: boolean
}

export function useCollaborationTeamsOverviewResolution({
  teamSearch,
  queriedTeamCount,
  isPlatformAdmin,
  viewerUserId,
  enabled,
}: UseCollaborationTeamsOverviewResolutionOptions): CollaborationTeamsOverviewResolution {
  const deferredTeamSearch = useDeferredValue(teamSearch)
  const memberCollaborationTeams = useGatewayMemberCollaborationTeams()
  const teamSearchTrimmed = teamSearch.trim()
  const isSearchStale = deferredTeamSearch.trim() !== teamSearchTrimmed

  const platformAdminSearchTeams = useGatewayTeamsBySearch(
    deferredTeamSearch,
    enabled && isPlatformAdmin && deferredTeamSearch.trim().length > 0
  )

  // 平台 admin 无搜索且团队数未超阈值时，后端按「全部协作团队」聚合 total/模型，
  // 故候选池也须取全部活跃团队（而非仅 membership），否则未加入团队的模型会被分组渲染丢弃。
  const adminBrowsesAllTeams =
    enabled &&
    isPlatformAdmin &&
    deferredTeamSearch.trim().length === 0 &&
    queriedTeamCount !== undefined &&
    queriedTeamCount <= COLLABORATION_TEAMS_REQUIRE_SEARCH_THRESHOLD
  const { data: allActiveTeams = [] } = useGatewayTeams(adminBrowsesAllTeams)

  const candidateTeams = useMemo(() => {
    if (!enabled) return []
    if (isPlatformAdmin) {
      if (deferredTeamSearch.trim().length > 0) {
        return filterCollaborationGatewayTeams(platformAdminSearchTeams)
      }
      if (adminBrowsesAllTeams) {
        return filterCollaborationGatewayTeams(allActiveTeams)
      }
    }
    return memberCollaborationTeams
  }, [
    adminBrowsesAllTeams,
    allActiveTeams,
    deferredTeamSearch,
    enabled,
    isPlatformAdmin,
    memberCollaborationTeams,
    platformAdminSearchTeams,
  ])

  const resolution = useMemo(() => {
    if (!enabled || queriedTeamCount === undefined) {
      return { teams: [], requiresSearch: false }
    }
    return resolveCollaborationTeamsCandidates({
      isPlatformAdmin,
      hasSearch: teamSearchTrimmed.length > 0,
      queriedTeamCount,
      candidateTeams,
      search: deferredTeamSearch,
      viewerUserId,
    })
  }, [
    candidateTeams,
    deferredTeamSearch,
    enabled,
    isPlatformAdmin,
    queriedTeamCount,
    teamSearchTrimmed.length,
    viewerUserId,
  ])

  return {
    teams: resolution.teams,
    requiresSearch: resolution.requiresSearch,
    isSearchStale,
  }
}

export function groupModelsByTenantId(
  models: readonly GatewayModel[]
): Map<string, GatewayModel[]> {
  return groupResourcesByTenantId(models, (model) => model.tenant_id ?? model.team_id ?? null)
}
