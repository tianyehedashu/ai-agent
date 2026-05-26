/**
 * Gateway 凭据相关 React Query key 与缓存失效。
 */

import { invalidateCredentialSummariesCache } from '@/features/gateway-credentials/use-credential-directory'

import type { QueryClient } from '@tanstack/react-query'

export const TEAM_CREDENTIALS_QUERY_KEY = ['gateway', 'credentials'] as const

export const MANAGED_TEAM_CREDENTIALS_QUERY_KEY = ['gateway', 'managed-team-credentials'] as const

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

export function invalidateGatewayCredentialCaches(
  queryClient: QueryClient,
  options?: Readonly<{ teamId?: string }>
): void {
  void queryClient.invalidateQueries({ queryKey: [...TEAM_CREDENTIALS_QUERY_KEY] })
  void queryClient.invalidateQueries({ queryKey: [...MANAGED_TEAM_CREDENTIALS_QUERY_KEY] })
  if (options?.teamId) {
    void queryClient.invalidateQueries({ queryKey: teamCredentialsListQueryKey(options.teamId) })
  }
  invalidateCredentialSummariesCache(queryClient)
}
