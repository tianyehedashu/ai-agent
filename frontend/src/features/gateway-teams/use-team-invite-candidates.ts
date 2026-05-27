import { useDeferredValue } from 'react'

import { useQuery } from '@tanstack/react-query'

import type { TeamInviteCandidateListResponse } from '@/api/gateway/teams'
import { teamsApi } from '@/api/gateway/teams'
import { GATEWAY_TEAMS_STALE_MS } from '@/features/gateway-teams/use-gateway-teams'

import type { UseQueryResult } from '@tanstack/react-query'

const DEFAULT_PAGE_SIZE = 20

export const teamInviteCandidatesQueryKey = (
  teamId: string,
  search: string | undefined,
  page: number,
  pageSize: number
) => ['gateway', 'teams', teamId, 'invite-candidates', { search, page, pageSize }] as const

export interface UseTeamInviteCandidatesOptions {
  teamId: string
  search: string
  page: number
  pageSize?: number
  enabled: boolean
}

export function useTeamInviteCandidates({
  teamId,
  search,
  page,
  pageSize = DEFAULT_PAGE_SIZE,
  enabled,
}: UseTeamInviteCandidatesOptions): UseQueryResult<TeamInviteCandidateListResponse> {
  const deferredSearch = useDeferredValue(search)
  const trimmedSearch = deferredSearch.trim() || undefined

  return useQuery({
    queryKey: teamInviteCandidatesQueryKey(teamId, trimmedSearch, page, pageSize),
    queryFn: () =>
      teamsApi.listInviteCandidates(teamId, {
        search: trimmedSearch,
        page,
        page_size: pageSize,
      }),
    enabled: enabled && teamId.length > 0,
    staleTime: GATEWAY_TEAMS_STALE_MS,
  })
}
