/**
 * Gateway 虚拟路由 React Query key 与缓存失效。
 */

import type { QueryClient } from '@tanstack/react-query'

export const TEAM_ROUTES_QUERY_KEY = ['gateway', 'routes'] as const

export const MANAGED_TEAM_ROUTES_QUERY_KEY = ['gateway', 'managed-team-routes'] as const

export function teamRoutesListQueryKey(teamId: string): readonly ['gateway', 'routes', string] {
  return [...TEAM_ROUTES_QUERY_KEY, teamId] as const
}

export function invalidateGatewayRouteCaches(queryClient: QueryClient): void {
  void queryClient.invalidateQueries({ queryKey: [...TEAM_ROUTES_QUERY_KEY] })
  void queryClient.invalidateQueries({ queryKey: [...MANAGED_TEAM_ROUTES_QUERY_KEY] })
}
