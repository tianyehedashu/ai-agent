/**
 * AI Gateway · 路由（Virtual Routing）
 *
 * Route 把一个「虚拟模型名」映射为一个 deployments 列表（含 primary 与三类 fallback）。
 * 调用方使用虚拟模型名 → Gateway 按策略选择 deployment → 上游凭据发起调用。
 */

import { apiClient } from '@/api/client'
import { buildPageQuerySearch, fetchAllPaginatedPages } from '@/lib/pagination'
import type { PaginatedList, PageQuery } from '@/types'

import { GATEWAY_API_BASE, teamGatewayPath } from './_base'

import type { GatewayModel } from './models'

export interface GatewayRoute {
  id: string
  tenant_id?: string | null
  team_id: string | null
  /** 团队自定义或系统级（只读） */
  source?: 'team' | 'system'
  /** 调用方传入的 `model` 字段值 */
  virtual_model: string
  primary_models: string[]
  /** 通用降级（如上游 5xx / timeout） */
  fallbacks_general: string[]
  /** 触发内容策略时的降级目标 */
  fallbacks_content_policy: string[]
  /** 上下文超长时的降级目标（更大窗口模型） */
  fallbacks_context_window: string[]
  /** 主选模型选择策略：simple-shuffle / weighted-pick / least-busy / ... */
  strategy: string
  retry_policy?: Record<string, unknown> | null
  enabled: boolean
}

export interface ManagedTeamRouteListResponse extends PaginatedList<GatewayRoute> {
  queried_team_count: number
  queried_personal_team_count: number
  queried_shared_team_count: number
  tenant_ids_with_routes: string[]
}

export interface GatewayRouteCreateBody {
  virtual_model: string
  primary_models: string[]
  fallbacks_general?: string[]
  fallbacks_content_policy?: string[]
  fallbacks_context_window?: string[]
  strategy?: string
  retry_policy?: Record<string, unknown> | null
}

/** PATCH /routes/{id}，与 RouteUpdate 对齐 */
export interface GatewayRouteUpdateBody {
  primary_models?: string[] | null
  fallbacks_general?: string[] | null
  fallbacks_content_policy?: string[] | null
  fallbacks_context_window?: string[] | null
  strategy?: string | null
  retry_policy?: Record<string, unknown> | null
  enabled?: boolean | null
}

/** GET /my-route-callable-models 单条（含跨团队 route_ref） */
export interface RouteCallableModel extends GatewayModel {
  route_ref: string
  team_kind: 'personal' | 'shared' | 'system'
  team_slug: string | null
  prefix_dispatchable: boolean
}

export type RouteCallableModelListResponse = PaginatedList<RouteCallableModel>

export interface ListMyRouteCallableModelsParams extends PageQuery {
  q?: string
  provider?: string
  team_id?: string
}

/** Routes 资源 API */
export const routesApi = {
  /** 列出 membership 内各团队可见的虚拟路由（跨团队聚合，分页） */
  listManagedTeamRoutesPage: (params?: PageQuery) =>
    apiClient.get<ManagedTeamRouteListResponse>(
      `${GATEWAY_API_BASE}/managed-team-routes`,
      buildPageQuerySearch(params)
    ),
  /** 拉取 membership 内全部可见虚拟路由（自动翻页） */
  listManagedTeamRoutes: () =>
    fetchAllPaginatedPages((page, page_size) =>
      routesApi.listManagedTeamRoutesPage({ page, page_size })
    ),
  /** 列出当前团队的虚拟路由 */
  listRoutes: (teamId: string) => apiClient.get<GatewayRoute[]>(teamGatewayPath(teamId, '/routes')),
  /** 创建路由 */
  createRoute: (teamId: string, body: GatewayRouteCreateBody) =>
    apiClient.post<GatewayRoute>(teamGatewayPath(teamId, '/routes'), body),
  /** 更新路由（含 fallbacks / strategy / enabled） */
  updateRoute: (teamId: string, id: string, body: GatewayRouteUpdateBody) =>
    apiClient.patch<GatewayRoute>(teamGatewayPath(teamId, `/routes/${id}`), body),
  /** 删除路由 */
  deleteRoute: (teamId: string, id: string) =>
    apiClient.delete<unknown>(teamGatewayPath(teamId, `/routes/${id}`)),

  listMyRouteCallableModelsPage: (params?: ListMyRouteCallableModelsParams) =>
    apiClient.get<RouteCallableModelListResponse>(
      `${GATEWAY_API_BASE}/my-route-callable-models`,
      buildPageQuerySearch(params)
    ),
  listMyRouteCallableModels: (
    params?: Omit<ListMyRouteCallableModelsParams, 'page' | 'page_size'>
  ) =>
    fetchAllPaginatedPages((page, page_size) =>
      routesApi.listMyRouteCallableModelsPage({ ...params, page, page_size })
    ),

  listMyRoutes: () => apiClient.get<GatewayRoute[]>(`${GATEWAY_API_BASE}/my-routes`),
  createMyRoute: (body: GatewayRouteCreateBody) =>
    apiClient.post<GatewayRoute>(`${GATEWAY_API_BASE}/my-routes`, body),
  updateMyRoute: (id: string, body: GatewayRouteUpdateBody) =>
    apiClient.patch<GatewayRoute>(`${GATEWAY_API_BASE}/my-routes/${id}`, body),
  deleteMyRoute: (id: string) => apiClient.delete<unknown>(`${GATEWAY_API_BASE}/my-routes/${id}`),
} as const
