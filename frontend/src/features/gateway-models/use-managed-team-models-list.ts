/**
 * 跨团队可管理团队模型聚合列表。
 */

import { useQuery, type UseQueryResult } from '@tanstack/react-query'

import {
  modelsApi,
  type ListManagedTeamModelsParams,
  type ManagedTeamModelListResponse,
} from '@/api/gateway/models'

export const MANAGED_TEAM_MODELS_QUERY_KEY = ['gateway', 'managed-team-models'] as const

export interface UseManagedTeamModelsListOptions extends ListManagedTeamModelsParams {
  enabled: boolean
}

export function useManagedTeamModelsList({
  enabled,
  search,
  page = 1,
  page_size: pageSize = 20,
  q,
  connectivity,
  provider,
  credential_id,
  type,
  enabled: modelEnabled,
}: UseManagedTeamModelsListOptions): UseQueryResult<ManagedTeamModelListResponse> {
  const trimmedTeamSearch = search !== undefined && search.trim() !== '' ? search.trim() : undefined
  const trimmedModelSearch = q !== undefined && q.trim() !== '' ? q.trim() : undefined

  return useQuery({
    queryKey: [
      ...MANAGED_TEAM_MODELS_QUERY_KEY,
      {
        search: trimmedTeamSearch,
        page,
        pageSize,
        q: trimmedModelSearch,
        connectivity,
        provider,
        credential_id,
        type,
        modelEnabled,
      },
    ],
    queryFn: () =>
      modelsApi.listManagedTeamModels({
        search: trimmedTeamSearch,
        page,
        page_size: pageSize,
        q: trimmedModelSearch,
        connectivity,
        provider,
        credential_id,
        type,
        enabled: modelEnabled,
      }),
    enabled,
  })
}
