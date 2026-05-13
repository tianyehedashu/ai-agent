/**
 * AI Gateway API Client
 *
 * 统一封装 /api/v1/gateway/* 管理端点。
 * 所有请求由 apiClient 注入 X-Team-Id（来自 gateway-team store）。
 */

import { apiClient } from '@/api/client'

// ============================
// Types（与后端 schemas/common.py 对齐）
// ============================

export interface GatewayTeam {
  id: string
  name: string
  slug: string
  kind: 'personal' | 'shared'
  owner_user_id: string
  /** 后端扩展角色时用 string；常见值 owner | admin | member */
  team_role?: string | null
  is_active?: boolean
  settings?: Record<string, unknown> | null
  created_at?: string
}

export interface TeamMember {
  id: string
  team_id: string
  user_id: string
  role: string
  created_at: string
}

export interface VirtualKey {
  id: string
  team_id: string
  name: string
  description?: string | null
  masked_key: string
  allowed_models: string[]
  allowed_capabilities: string[]
  rpm_limit: number | null
  tpm_limit: number | null
  store_full_messages: boolean
  guardrail_enabled: boolean
  is_active: boolean
  is_system: boolean
  expires_at: string | null
  last_used_at: string | null
  usage_count: number
  created_at: string
}

export interface VirtualKeyCreated extends VirtualKey {
  plain_key: string
}

export interface ProviderCredential {
  id: string
  scope: 'system' | 'team' | 'user'
  scope_id: string | null
  provider: string
  name: string
  api_base: string | null
  is_active: boolean
  extra: Record<string, unknown> | null
  created_at: string
}

export interface GatewayModel {
  id: string
  team_id: string | null
  name: string
  capability: string
  real_model: string
  credential_id: string
  provider: string
  weight: number
  rpm_limit: number | null
  tpm_limit: number | null
  enabled: boolean
  tags?: Record<string, unknown> | null
  created_at: string
}

export interface GatewayModelPreset {
  id: string
  name: string
  provider: string
  real_model: string
  capability: string
  context_window: number
  input_price: number
  output_price: number
  supports_vision: boolean
  supports_tools: boolean
  supports_reasoning: boolean
  recommended_for: string[]
  description: string
}

export interface GatewayModelCreateBody {
  name: string
  capability: string
  real_model: string
  credential_id: string
  provider: string
  weight?: number
  rpm_limit?: number | null
  tpm_limit?: number | null
  tags?: Record<string, unknown> | null
}

export interface GatewayRoute {
  id: string
  team_id: string | null
  virtual_model: string
  primary_models: string[]
  fallbacks_general: string[]
  fallbacks_content_policy: string[]
  fallbacks_context_window: string[]
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

export interface GatewayBudget {
  id: string
  scope: 'system' | 'team' | 'key' | 'user'
  scope_id: string | null
  period: 'daily' | 'monthly' | 'total'
  limit_usd: number | null
  limit_tokens: number | null
  limit_requests: number | null
  current_usd: number
  current_tokens: number
  current_requests: number
  reset_at: string | null
}

/** PUT /budgets 请求体（与 BudgetUpsert 一致） */
export interface BudgetUpsertBody {
  scope: 'system' | 'team' | 'key' | 'user'
  scope_id?: string | null
  period: 'daily' | 'monthly' | 'total'
  limit_usd?: number | null
  limit_tokens?: number | null
  limit_requests?: number | null
}

export interface DashboardSummary {
  total_requests: number
  total_input_tokens: number
  total_output_tokens: number
  /** 后端 Decimal 序列化常为 JSON 字符串 */
  total_cost_usd: number | string
  success_count: number
  failure_count: number
  avg_latency_ms: number
  success_rate: number
}

/**
 * 管理面日志/大盘用量切片（与 Tenancy Team.kind、预算 BudgetUpsert.scope 无关）。
 * - workspace：按当前 X-Team-Id 工作区（含 personal/shared）过滤/聚合。
 * - user：按当前登录用户跨工作区聚合。
 */
export type GatewayUsageAggregation = 'workspace' | 'user'

export interface GatewayLogItem {
  id: string
  created_at: string
  team_id: string | null
  user_id: string | null
  vkey_id: string | null
  capability: string
  route_name: string | null
  real_model: string | null
  provider: string | null
  status: string
  error_code: string | null
  input_tokens: number
  output_tokens: number
  cached_tokens: number
  cost_usd: number | string
  latency_ms: number
  cache_hit: boolean
  fallback_chain: string[]
  request_id: string | null
  user_email_snapshot: string | null
  vkey_name_snapshot: string | null
}

export interface AlertRule {
  id: string
  team_id: string | null
  name: string
  description: string | null
  metric: string
  threshold: number
  window_minutes: number
  channels: Record<string, unknown>
  enabled: boolean
  last_triggered_at: string | null
  created_at: string
}

/** POST /alerts/rules 请求体 */
export interface AlertRuleCreateBody {
  name: string
  description?: string | null
  metric: 'error_rate' | 'budget_usage' | 'latency_p95' | 'request_rate'
  threshold: number
  window_minutes?: number
  channels?: Record<string, unknown>
  enabled?: boolean
}

// ============================
// API
// ============================

const base = '/api/v1/gateway'

export const gatewayApi = {
  listTeams: () => apiClient.get<GatewayTeam[]>(`${base}/teams`),
  createTeam: (body: { name: string; slug?: string }) =>
    apiClient.post<GatewayTeam>(`${base}/teams`, body),
  deleteTeam: (id: string) => apiClient.delete<unknown>(`${base}/teams/${id}`),
  listMembers: (teamId: string) => apiClient.get<TeamMember[]>(`${base}/teams/${teamId}/members`),
  addMember: (teamId: string, body: { user_id: string; role: string }) =>
    apiClient.post<TeamMember>(`${base}/teams/${teamId}/members`, body),
  removeMember: (teamId: string, userId: string) =>
    apiClient.delete<unknown>(`${base}/teams/${teamId}/members/${userId}`),

  listKeys: () => apiClient.get<VirtualKey[]>(`${base}/keys`),
  createKey: (body: {
    name: string
    allowed_models?: string[]
    allowed_capabilities?: string[]
    rpm_limit?: number | null
    tpm_limit?: number | null
    store_full_messages?: boolean
    guardrail_enabled?: boolean
  }) => apiClient.post<VirtualKeyCreated>(`${base}/keys`, body),
  revokeKey: (id: string) => apiClient.delete<unknown>(`${base}/keys/${id}`),

  listCredentials: () => apiClient.get<ProviderCredential[]>(`${base}/credentials`),
  createCredential: (body: {
    provider: string
    name: string
    api_key: string
    api_base?: string
    extra?: Record<string, unknown>
  }) => apiClient.post<ProviderCredential>(`${base}/credentials`, body),
  deleteCredential: (id: string) => apiClient.delete<unknown>(`${base}/credentials/${id}`),

  listModels: () => apiClient.get<GatewayModel[]>(`${base}/models`),
  listModelPresets: () => apiClient.get<GatewayModelPreset[]>(`${base}/models/presets`),
  createModel: (body: GatewayModelCreateBody) =>
    apiClient.post<GatewayModel>(`${base}/models`, body),
  deleteModel: (id: string) => apiClient.delete<unknown>(`${base}/models/${id}`),

  listRoutes: () => apiClient.get<GatewayRoute[]>(`${base}/routes`),
  createRoute: (body: GatewayRouteCreateBody) =>
    apiClient.post<GatewayRoute>(`${base}/routes`, body),
  deleteRoute: (id: string) => apiClient.delete<unknown>(`${base}/routes/${id}`),

  listBudgets: () => apiClient.get<GatewayBudget[]>(`${base}/budgets`),
  upsertBudget: (body: BudgetUpsertBody) => apiClient.put<GatewayBudget>(`${base}/budgets`, body),
  deleteBudget: (id: string) => apiClient.delete<unknown>(`${base}/budgets/${id}`),

  listLogs: (params?: {
    /** 默认 workspace */
    usage_aggregation?: GatewayUsageAggregation
    page?: number
    page_size?: number
    capability?: string
    status?: string
    start?: string
    end?: string
    vkey_id?: string
  }) =>
    apiClient.get<{
      items: GatewayLogItem[]
      total: number
      page: number
      page_size: number
    }>(`${base}/logs`, params),
  getLog: (id: string, params?: { usage_aggregation?: GatewayUsageAggregation }) =>
    apiClient.get<GatewayLogItem>(`${base}/logs/${id}`, params),

  dashboard: (params?: { days?: number; usage_aggregation?: GatewayUsageAggregation }) =>
    apiClient.get<DashboardSummary>(`${base}/dashboard/summary`, params),

  listAlerts: () => apiClient.get<AlertRule[]>(`${base}/alerts/rules`),
  createAlert: (body: AlertRuleCreateBody) =>
    apiClient.post<AlertRule>(`${base}/alerts/rules`, body),
  deleteAlert: (id: string) => apiClient.delete<unknown>(`${base}/alerts/rules/${id}`),

  importFromUserConfig: () => apiClient.post<{ created: number }>(`${base}/credentials/import`),
}
