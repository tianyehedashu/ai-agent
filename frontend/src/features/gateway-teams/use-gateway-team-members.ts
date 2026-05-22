/**
 * Gateway 团队成员列表（React Query 去重）
 */

import { useQuery } from '@tanstack/react-query'

import { teamsApi, type TeamMember } from '@/api/gateway/teams'

import type { UseQueryResult } from '@tanstack/react-query'

export function gatewayTeamMembersQueryKey(
  teamId: string
): readonly ['gateway', 'team-members', string] {
  return ['gateway', 'team-members', teamId]
}

export function useGatewayTeamMembers(teamId: string): UseQueryResult<TeamMember[]> {
  return useQuery({
    queryKey: gatewayTeamMembersQueryKey(teamId),
    queryFn: () => teamsApi.listMembers(teamId),
    enabled: Boolean(teamId),
  })
}
