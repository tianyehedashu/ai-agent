/**
 * 跨团队共享授权（路由即可共享模型 · 委派）React Query hooks
 *
 * - owner 侧：列授权 / 可共享团队 / 发布 / 改别名 / 撤销
 * - team 侧：列共享进来的路由 / 踢出
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query'

import {
  routesApi,
  type RouteGrant,
  type RouteGrantableTeam,
  type SharedRoute,
} from '@/api/gateway/routes'
import { invalidateGatewayModelsAvailableCaches } from '@/features/gateway-models/query-keys'

export function routeGrantsQueryKey(routeId: string): readonly ['gateway', 'route-grants', string] {
  return ['gateway', 'route-grants', routeId]
}

export function routeGrantableTeamsQueryKey(
  routeId: string
): readonly ['gateway', 'route-grantable-teams', string] {
  return ['gateway', 'route-grantable-teams', routeId]
}

export function sharedRoutesQueryKey(
  teamId: string
): readonly ['gateway', 'shared-routes', string] {
  return ['gateway', 'shared-routes', teamId]
}

export function useRouteGrants(
  routeId: string,
  options?: { enabled?: boolean }
): UseQueryResult<RouteGrant[]> {
  return useQuery({
    queryKey: routeGrantsQueryKey(routeId),
    queryFn: () => routesApi.listRouteGrants(routeId),
    enabled: options?.enabled ?? Boolean(routeId),
  })
}

export function useRouteGrantableTeams(
  routeId: string,
  options?: { enabled?: boolean }
): UseQueryResult<RouteGrantableTeam[]> {
  return useQuery({
    queryKey: routeGrantableTeamsQueryKey(routeId),
    queryFn: () => routesApi.listRouteGrantableTeams(routeId),
    enabled: options?.enabled ?? Boolean(routeId),
  })
}

export function useSharedRoutes(
  teamId: string,
  options?: { enabled?: boolean }
): UseQueryResult<SharedRoute[]> {
  return useQuery({
    queryKey: sharedRoutesQueryKey(teamId),
    queryFn: () => routesApi.listSharedRoutes(teamId),
    enabled: options?.enabled ?? Boolean(teamId),
  })
}

export function useGrantRouteToTeam(
  routeId: string
): UseMutationResult<
  RouteGrant,
  Error,
  { target_tenant_id: string; exposed_alias?: string | null }
> {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { target_tenant_id: string; exposed_alias?: string | null }) =>
      routesApi.grantRouteToTeam(routeId, body),
    onSuccess: (_data, variables) => {
      void qc.invalidateQueries({ queryKey: routeGrantsQueryKey(routeId) })
      void qc.invalidateQueries({ queryKey: routeGrantableTeamsQueryKey(routeId) })
      void qc.invalidateQueries({ queryKey: sharedRoutesQueryKey(variables.target_tenant_id) })
      invalidateGatewayModelsAvailableCaches(qc)
    },
  })
}

export function useUpdateRouteGrantAlias(
  routeId: string
): UseMutationResult<RouteGrant, Error, { tenantId: string; exposed_alias: string }> {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ tenantId, exposed_alias }: { tenantId: string; exposed_alias: string }) =>
      routesApi.updateRouteGrantAlias(routeId, tenantId, { exposed_alias }),
    onSuccess: (_data, variables) => {
      void qc.invalidateQueries({ queryKey: routeGrantsQueryKey(routeId) })
      void qc.invalidateQueries({ queryKey: sharedRoutesQueryKey(variables.tenantId) })
      invalidateGatewayModelsAvailableCaches(qc)
    },
  })
}

export function useRevokeRouteGrant(routeId: string): UseMutationResult<unknown, Error, string> {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (tenantId: string) => routesApi.revokeRouteGrant(routeId, tenantId),
    onSuccess: (_data, tenantId) => {
      void qc.invalidateQueries({ queryKey: routeGrantsQueryKey(routeId) })
      void qc.invalidateQueries({ queryKey: routeGrantableTeamsQueryKey(routeId) })
      void qc.invalidateQueries({ queryKey: sharedRoutesQueryKey(tenantId) })
      invalidateGatewayModelsAvailableCaches(qc)
    },
  })
}

export function useEjectSharedRoute(teamId: string): UseMutationResult<unknown, Error, string> {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (grantId: string) => routesApi.ejectSharedRoute(teamId, grantId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: sharedRoutesQueryKey(teamId) })
      invalidateGatewayModelsAvailableCaches(qc)
    },
  })
}
