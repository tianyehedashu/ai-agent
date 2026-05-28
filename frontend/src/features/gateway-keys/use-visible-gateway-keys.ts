import { useQuery } from '@tanstack/react-query'

import { gatewayApi, type VirtualKey } from '@/api/gateway'
import { GATEWAY_MODELS_STALE_MS } from '@/features/gateway-models/utils'

export const MANAGED_TEAM_KEYS_QUERY_KEY = ['gateway', 'managed-team-keys'] as const

export interface VisibleGatewayKeysResult {
  keys: VirtualKey[]
  isLoading: boolean
  isFetching: boolean
  isError: boolean
  error: unknown
  refetch: () => Promise<unknown>
}

/** 当前用户 membership 内各团队下自建的虚拟 Key（单次聚合 API） */
export function useVisibleGatewayKeys(): VisibleGatewayKeysResult {
  const query = useQuery({
    queryKey: MANAGED_TEAM_KEYS_QUERY_KEY,
    queryFn: () => gatewayApi.listManagedTeamKeys(),
    staleTime: GATEWAY_MODELS_STALE_MS,
  })

  return {
    keys: query.data ?? [],
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    isError: query.isError,
    error: query.error,
    refetch: () => query.refetch(),
  }
}
