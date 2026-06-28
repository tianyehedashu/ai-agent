import { useQuery, type UseQueryResult } from '@tanstack/react-query'

import { adminUsersApi, type PlatformRole, type PlatformUserListResponse } from '@/api/admin-users'
import { GATEWAY_TEAMS_STALE_MS } from '@/features/gateway-teams/use-gateway-teams'
import { DEFAULT_PAGE_SIZE } from '@/lib/pagination'

import { PLATFORM_USERS_QUERY_KEY } from './query-keys'

export interface UsePlatformUsersListOptions {
  search: string
  role: PlatformRole | 'all'
  isActive: 'all' | 'active' | 'inactive'
  page: number
  pageSize?: number
  enabled: boolean
}

export function usePlatformUsersList({
  search,
  role,
  isActive,
  page,
  pageSize = DEFAULT_PAGE_SIZE,
  enabled,
}: UsePlatformUsersListOptions): UseQueryResult<PlatformUserListResponse> {
  const trimmedSearch = search.trim() || undefined
  const roleFilter = role === 'all' ? undefined : role
  const isActiveFilter = isActive === 'all' ? undefined : isActive === 'active'

  return useQuery({
    queryKey: [
      ...PLATFORM_USERS_QUERY_KEY,
      { search: trimmedSearch, role: roleFilter, isActive: isActiveFilter, page, pageSize },
    ],
    queryFn: () =>
      adminUsersApi.list({
        search: trimmedSearch,
        role: roleFilter,
        is_active: isActiveFilter,
        page,
        page_size: pageSize,
      }),
    enabled,
    staleTime: GATEWAY_TEAMS_STALE_MS,
  })
}
