/**
 * 单团队路由列表（React Query 去重）
 */

import { useQuery, type UseQueryOptions, type UseQueryResult } from '@tanstack/react-query'

import { routesApi, type GatewayRoute } from '@/api/gateway/routes'

export function gatewayRoutesQueryKey(teamId: string): readonly ['gateway', 'routes', string] {
  return ['gateway', 'routes', teamId]
}

export function useGatewayRoutes(
  teamId: string,
  options?: Pick<UseQueryOptions<GatewayRoute[]>, 'enabled' | 'staleTime'>
): UseQueryResult<GatewayRoute[]> {
  return useQuery({
    queryKey: gatewayRoutesQueryKey(teamId),
    queryFn: () => routesApi.listRoutes(teamId),
    enabled: options?.enabled ?? Boolean(teamId),
    staleTime: options?.staleTime,
  })
}
