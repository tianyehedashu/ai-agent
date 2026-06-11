/**
 * 单团队虚拟 Key 列表（React Query 去重）
 */

import { useQuery, type UseQueryOptions, type UseQueryResult } from '@tanstack/react-query'

import { keysApi, type VirtualKey } from '@/api/gateway/keys'

export function gatewayVirtualKeysQueryKey(teamId: string): readonly ['gateway', 'keys', string] {
  return ['gateway', 'keys', teamId]
}

export function useGatewayVirtualKeys(
  teamId: string,
  options?: Pick<UseQueryOptions<VirtualKey[]>, 'enabled' | 'staleTime'>
): UseQueryResult<VirtualKey[]> {
  return useQuery({
    queryKey: gatewayVirtualKeysQueryKey(teamId),
    queryFn: () => keysApi.listKeys(teamId),
    enabled: options?.enabled ?? Boolean(teamId),
    staleTime: options?.staleTime,
  })
}
