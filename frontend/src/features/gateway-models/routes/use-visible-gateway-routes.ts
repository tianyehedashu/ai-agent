import { useMemo } from 'react'

import { useQueries } from '@tanstack/react-query'

import { gatewayApi, type GatewayRoute } from '@/api/gateway'
import { GATEWAY_MODELS_STALE_MS } from '@/features/gateway-models/utils'
import { useGatewayMembershipTeamIds } from '@/hooks/use-gateway-team-id'

function mergeVisibleRoutes(lists: readonly GatewayRoute[][]): GatewayRoute[] {
  const byId = new Map<string, GatewayRoute>()
  for (const list of lists) {
    for (const route of list) {
      byId.set(route.id, route)
    }
  }
  return [...byId.values()].sort((a, b) => a.virtual_model.localeCompare(b.virtual_model))
}

export function resolveGatewayRouteTeamId(route: GatewayRoute): string | null {
  return route.team_id ?? route.tenant_id ?? null
}

export interface VisibleGatewayRoutesResult {
  routes: GatewayRoute[]
  isLoading: boolean
  isFetching: boolean
  isError: boolean
  error: unknown
  refetch: () => Promise<unknown[]>
}

/** 聚合当前用户 membership 内各团队可见的虚拟路由（系统路由按 id 去重） */
export function useVisibleGatewayRoutes(): VisibleGatewayRoutesResult {
  const teamIds = useGatewayMembershipTeamIds()

  const queries = useQueries({
    queries: teamIds.map((teamId) => ({
      queryKey: ['gateway', 'routes', teamId] as const,
      queryFn: () => gatewayApi.listRoutes(teamId),
      staleTime: GATEWAY_MODELS_STALE_MS,
      enabled: teamIds.length > 0,
    })),
  })

  const routes = useMemo(
    () => mergeVisibleRoutes(queries.map((query) => query.data ?? [])),
    [queries]
  )

  return {
    routes,
    isLoading: teamIds.length > 0 && queries.some((query) => query.isLoading),
    isFetching: queries.some((query) => query.isFetching),
    isError: queries.some((query) => query.isError),
    error: queries.find((query) => query.error)?.error,
    refetch: () => Promise.all(queries.map((query) => query.refetch())),
  }
}
