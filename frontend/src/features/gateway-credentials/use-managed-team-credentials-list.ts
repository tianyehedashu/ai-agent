/**
 * 跨团队可管理凭据聚合列表（单次 query，服务端分页 + search）。
 */

import { useQuery, type UseQueryResult } from '@tanstack/react-query'

import { credentialsApi, type ManagedTeamCredentialListResponse } from '@/api/gateway/credentials'

import { MANAGED_TEAM_CREDENTIALS_QUERY_KEY } from './query-keys'

export interface UseManagedTeamCredentialsListOptions {
  search: string
  page: number
  pageSize?: number
  enabled: boolean
}

export function useManagedTeamCredentialsList({
  search,
  page,
  pageSize = 20,
  enabled,
}: UseManagedTeamCredentialsListOptions): UseQueryResult<ManagedTeamCredentialListResponse> {
  const trimmedSearch = search.trim() || undefined

  return useQuery({
    queryKey: [...MANAGED_TEAM_CREDENTIALS_QUERY_KEY, { search: trimmedSearch, page, pageSize }],
    queryFn: () =>
      credentialsApi.listManagedTeamCredentials({
        search: trimmedSearch,
        page,
        page_size: pageSize,
      }),
    enabled,
  })
}
