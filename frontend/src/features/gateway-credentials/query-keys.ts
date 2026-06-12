/**
 * Gateway 凭据相关 React Query key 与缓存失效。
 */

import { invalidateCredentialSummariesCache } from '@/features/gateway-credentials/use-credential-directory'

import type { QueryClient } from '@tanstack/react-query'

export const TEAM_CREDENTIALS_QUERY_KEY = ['gateway', 'credentials'] as const

export const MANAGED_TEAM_CREDENTIALS_QUERY_KEY = ['gateway', 'managed-team-credentials'] as const

export const MY_CREDENTIALS_QUERY_KEY = ['gateway', 'my-credentials'] as const

export function teamCredentialsListQueryKey(
  teamId: string
): readonly ['gateway', 'credentials', string] {
  return [...TEAM_CREDENTIALS_QUERY_KEY, teamId] as const
}

export function systemCredentialsTabQueryKey(
  teamId: string
): readonly ['gateway', 'credentials', string, 'system-tab'] {
  return [...TEAM_CREDENTIALS_QUERY_KEY, teamId, 'system-tab'] as const
}

export function credentialDetailQueryKey(
  teamId: string,
  credentialId: string
): readonly ['gateway', 'credential', string, string] {
  return ['gateway', 'credential', teamId, credentialId] as const
}

export interface InvalidateGatewayCredentialCachesOptions {
  teamId?: string
  credentialId?: string
  credentialTeamId?: string
  includeBudgets?: boolean
  includeModels?: boolean
}

export function invalidateGatewayCredentialCaches(
  queryClient: QueryClient,
  options?: InvalidateGatewayCredentialCachesOptions
): void {
  void queryClient.invalidateQueries({ queryKey: [...TEAM_CREDENTIALS_QUERY_KEY] })
  void queryClient.invalidateQueries({ queryKey: [...MANAGED_TEAM_CREDENTIALS_QUERY_KEY] })
  void queryClient.invalidateQueries({ queryKey: [...MY_CREDENTIALS_QUERY_KEY] })
  void queryClient.invalidateQueries({ queryKey: ['gateway', 'unified-credentials'] })
  void queryClient.invalidateQueries({
    queryKey: ['gateway', 'playground', 'credential-summaries'],
  })
  if (options?.teamId) {
    void queryClient.invalidateQueries({ queryKey: teamCredentialsListQueryKey(options.teamId) })
  }
  const detailTeamId = options?.credentialTeamId ?? options?.teamId
  if (detailTeamId && options?.credentialId) {
    void queryClient.invalidateQueries({
      queryKey: credentialDetailQueryKey(detailTeamId, options.credentialId),
    })
  }
  if (options?.includeBudgets) {
    void queryClient.invalidateQueries({ queryKey: ['gateway', 'budgets'] })
  }
  if (options?.includeModels) {
    void queryClient.invalidateQueries({ queryKey: ['gateway', 'models'] })
    void queryClient.invalidateQueries({ queryKey: ['gateway', 'my-models'] })
  }
  invalidateCredentialSummariesCache(queryClient)
}
