/**
 * AI Gateway · 路由（Virtual Routing）
 *
 * Route 把一个「虚拟模型名」映射为一个 deployments 列表（含 primary 与三类 fallback）。
 * 调用方使用虚拟模型名 → Gateway 按策略选择 deployment → 上游凭据发起调用。
 */

import { apiClient } from '@/api/client'

import { GATEWAY_API_BASE } from './_base'

export interface GatewayRoute {
  id: string
  team_id: string | null
  /** 调用方传入的 `model` 字段值 */
  virtual_model: string
  primary_models: string[]
  /** 通用降级（如上游 5xx / timeout） */
  fallbacks_general: string[]
  /** 触发内容策略时的降级目标 */
  fallbacks_content_policy: string[]
  /** 上下文超长时的降级目标（更大窗口模型） */
  fallbacks_context_window: string[]
  /** 主选模型选择策略：weighted / round-robin / ... */
  strategy: string
  retry_policy?: Record<string, unknown> | null
  enabled: boolean
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

/** Routes 资源 API */
export const routesApi = {
  /** 列出当前团队的虚拟路由 */
  listRoutes: () => apiClient.get<GatewayRoute[]>(`${GATEWAY_API_BASE}/routes`),
  /** 创建路由 */
  createRoute: (body: GatewayRouteCreateBody) =>
    apiClient.post<GatewayRoute>(`${GATEWAY_API_BASE}/routes`, body),
  /** 更新路由（含 fallbacks / strategy / enabled） */
  updateRoute: (id: string, body: GatewayRouteUpdateBody) =>
    apiClient.patch<GatewayRoute>(`${GATEWAY_API_BASE}/routes/${id}`, body),
  /** 删除路由 */
  deleteRoute: (id: string) => apiClient.delete<unknown>(`${GATEWAY_API_BASE}/routes/${id}`),
} as const
