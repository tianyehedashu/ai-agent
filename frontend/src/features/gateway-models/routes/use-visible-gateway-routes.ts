import { useQuery } from '@tanstack/react-query'

import { gatewayApi, type GatewayRoute } from '@/api/gateway'
import { MANAGED_TEAM_ROUTES_QUERY_KEY } from '@/features/gateway-models/routes/query-keys'
import { GATEWAY_MODELS_STALE_MS } from '@/features/gateway-models/utils'

export function resolveGatewayRouteTeamId(route: GatewayRoute): string | null {
  return route.team_id ?? route.tenant_id ?? null
}

export { MANAGED_TEAM_ROUTES_QUERY_KEY } from '@/features/gateway-models/routes/query-keys'

export interface VisibleGatewayRoutesResult {
  routes: GatewayRoute[]
  isLoading: boolean
  isFetching: boolean
  isError: boolean
  error: unknown
  refetch: () => Promise<unknown>
}

/** 当前用户 membership 内各团队可见的虚拟路由（单次聚合 API） */
export function useVisibleGatewayRoutes(): VisibleGatewayRoutesResult {
  const query = useQuery({
    queryKey: MANAGED_TEAM_ROUTES_QUERY_KEY,
    queryFn: () => gatewayApi.listManagedTeamRoutes(),
    staleTime: GATEWAY_MODELS_STALE_MS,
  })

  return {
    routes: query.data ?? [],
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    isError: query.isError,
    error: query.error,
    refetch: () => query.refetch(),
  }
}
