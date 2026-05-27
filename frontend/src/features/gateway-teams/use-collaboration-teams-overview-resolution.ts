/**
 * 协作团队分组列表：团队候选解析（凭据/模型共用）。
 */

import { useDeferredValue, useMemo } from 'react'

import type { GatewayModel } from '@/api/gateway'
import type { GatewayTeam } from '@/api/gateway/teams'
import { filterCollaborationGatewayTeams } from '@/features/gateway-teams/gateway-team-collaboration'
import {
  groupResourcesByTenantId,
  resolveCollaborationTeamsCandidates,
} from '@/features/gateway-teams/resolve-collaboration-teams-candidates'
import {
  useGatewayTeamsBySearch,
  useGatewayWritableCollaborationTeams,
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
  const writableCollaborationTeams = useGatewayWritableCollaborationTeams()
  const teamSearchTrimmed = teamSearch.trim()
  const isSearchStale = deferredTeamSearch.trim() !== teamSearchTrimmed

  const platformAdminSearchTeams = useGatewayTeamsBySearch(
    deferredTeamSearch,
    enabled && isPlatformAdmin && deferredTeamSearch.trim().length > 0
  )

  const candidateTeams = useMemo(() => {
    if (!enabled) return []
    if (isPlatformAdmin && deferredTeamSearch.trim().length > 0) {
      return filterCollaborationGatewayTeams(platformAdminSearchTeams)
    }
    return writableCollaborationTeams
  }, [
    deferredTeamSearch,
    enabled,
    isPlatformAdmin,
    platformAdminSearchTeams,
    writableCollaborationTeams,
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
