import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { grantsApi } from '@/api/gateway/grants'
import { gatewayVirtualKeysQueryKey } from '@/features/gateway-keys/use-gateway-virtual-keys'

export function grantsQueryKey(teamId: string, vkeyId: string): readonly string[] {
  return ['gateway', 'vkey-grants', teamId, vkeyId]
}

export function grantableTeamsQueryKey(teamId: string, vkeyId: string): readonly string[] {
  return ['gateway', 'vkey-grantable-teams', teamId, vkeyId]
}

export function useVkeyGrants(teamId: string, vkeyId: string, enabled: boolean) {
  return useQuery({
    queryKey: grantsQueryKey(teamId, vkeyId),
    queryFn: () => grantsApi.listGrants(teamId, vkeyId),
    enabled,
  })
}

export function useGrantableTeams(teamId: string, vkeyId: string, enabled: boolean) {
  return useQuery({
    queryKey: grantableTeamsQueryKey(teamId, vkeyId),
    queryFn: () => grantsApi.listGrantableTeams(teamId, vkeyId),
    enabled,
  })
}

function invalidateGrantQueries(
  queryClient: ReturnType<typeof useQueryClient>,
  teamId: string,
  vkeyId: string
): void {
  void queryClient.invalidateQueries({ queryKey: grantsQueryKey(teamId, vkeyId) })
  void queryClient.invalidateQueries({ queryKey: grantableTeamsQueryKey(teamId, vkeyId) })
  void queryClient.invalidateQueries({ queryKey: gatewayVirtualKeysQueryKey(teamId) })
  void queryClient.invalidateQueries({ queryKey: ['gateway', 'managed-team-keys'] })
}

export function useGrantMutations(teamId: string, vkeyId: string) {
  const queryClient = useQueryClient()

  const addMutation = useMutation({
    mutationFn: (tenantIds: string[]) =>
      grantsApi.grantToTeams(teamId, vkeyId, { tenant_ids: tenantIds }),
    onSuccess: () => {
      invalidateGrantQueries(queryClient, teamId, vkeyId)
    },
  })

  const revokeMutation = useMutation({
    mutationFn: (tenantId: string) => grantsApi.revokeGrant(teamId, vkeyId, tenantId),
    onSuccess: () => {
      invalidateGrantQueries(queryClient, teamId, vkeyId)
    },
  })

  return { addMutation, revokeMutation }
}
