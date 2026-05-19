/**
 * AI Gateway API Client
 *
 * 统一封装 /api/v1/gateway/* 管理端点。
 * 所有请求由 apiClient 注入 X-Team-Id（来自 gateway-team store）。
 */

import { apiClient } from '@/api/client'
import type { DisplayCurrency, MoneyDisplay } from '@/types/money'
import type { AvailableModelsResponse, ModelTestStatus, ModelType } from '@/types/user-model'

// ============================
// 模型连通性测试（与 backend model_test_constants 对齐）
// ============================

/** 与 ``GATEWAY_MODEL_TEST_SUPPORTED_CAPABILITIES``（Python）一致。 */
export const GATEWAY_MODEL_TEST_SUPPORTED_CAPABILITIES = ['chat', 'embedding', 'image'] as const

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

export type VirtualKeyBatchRevokeReason = 'not_found' | 'permission_denied' | 'system_key'

export interface VirtualKeyBatchRevokeFailure {
  key_id: string
  reason: VirtualKeyBatchRevokeReason
}

export interface VirtualKeyBatchRevokeResult {
  revoked: string[]
  failed: VirtualKeyBatchRevokeFailure[]
}

export interface ProviderCredential {
  id: string
  scope: 'system' | 'team' | 'user'
  scope_id: string | null
  provider: string
  name: string
  api_base: string | null
  is_active: boolean
  /** app.toml/环境变量同步托管的 system 凭据 */
  is_config_managed?: boolean
  extra: Record<string, unknown> | null
  created_at: string
  /** 后端解密后掩码展示，不含完整密钥 */
  api_key_masked: string
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
  /** 选择器用特性类型（后端由 tags + capability 推导） */
  model_types?: string[]
  /** 与 ModelCapabilitySnapshot 对齐的扁平特性 */
  selector_capabilities?: Record<string, unknown>
  /** 上次连通性测试结果，未测过为 null */
  last_test_status: ModelTestStatus
  /** 上次连通性测试时间（ISO 8601），未测过为 null */
  last_tested_at: string | null
  /** 上次失败/不支持时的说明；成功或未测过为 null */
  last_test_reason: string | null
  /** 当前调用方客户套餐命中状态；管理列表可缺省 */
  entitlement_status?: 'active' | 'exhausted' | 'resetting' | 'expired' | 'none'
  entitlement_reset_at?: string | null
  created_at: string
}

/** 与 GET /models/usage-summary 对齐；用量按日志 route_name = 注册名统计。 */
export interface GatewayModelRouteUsageSlice {
  requests: number
  input_tokens: number
  output_tokens: number
  /** 后端 Decimal 序列化常为 JSON 字符串 */
  cost_usd: number | string
}

export interface GatewayModelRouteUsageItem {
  route_name: string
  workspace: GatewayModelRouteUsageSlice
  user: GatewayModelRouteUsageSlice
}

export interface GatewayModelUsageSummary {
  start: string
  end: string
  items: GatewayModelRouteUsageItem[]
}

/** GET /admin/credential-stats（仅平台管理员） */
export interface PlatformCredentialStat {
  credential_id: string
  provider: string
  name: string
  scope: string
  scope_id: string | null
  is_active: boolean
  gateway_model_count: number
  requests: number
  input_tokens: number
  output_tokens: number
  cost_usd: number | string
  success_count: number
  failure_count: number
}

export interface GatewayModelTestResult {
  success: boolean
  message: string
  model: string
  status: string
  tested_at: string
  reason: string | null
  response_preview?: string
}

/** GET /my-models 列表项（与模型选择器 personal 段形状对齐） */
export interface PersonalGatewayModel {
  id: string
  user_id: string | null
  anonymous_user_id: string | null
  display_name: string
  provider: string
  model_id: string
  api_key_masked: string | null
  has_api_key: boolean
  api_base: string | null
  credential_id: string
  model_types: ModelType[]
  config: Record<string, unknown> | null
  is_active: boolean
  is_system: boolean
  capability: string
  name: string
  last_test_status: ModelTestStatus
  last_tested_at: string | null
  last_test_reason: string | null
  /** 当前调用方客户套餐命中状态；管理列表可缺省 */
  entitlement_status?: 'active' | 'exhausted' | 'resetting' | 'expired' | 'none'
  entitlement_reset_at?: string | null
  created_at: string | null
  updated_at: string | null
}

export interface PersonalGatewayModelCreateBody {
  display_name: string
  provider: string
  model_id: string
  credential_id: string
  model_types: ModelType[]
  tags?: Record<string, unknown> | null
}

// --- 凭据上游探测 / 批量导入（与 presentation/schemas/credential_upstream_catalog.py 对齐） ---

export type CredentialProbeSupport = 'full' | 'partial' | 'unsupported' | 'error'

export type CredentialProbeUpstream = 'openai_compatible' | 'none'

export interface CredentialUpstreamItem {
  id: string
  owned_by?: string | null
  /** 该上游 id 在本凭据下是否已有注册行 */
  already_registered?: boolean
  /** 已注册的 Gateway 别名（route name） */
  registered_names?: string[]
}

export interface CredentialProbeResult {
  credential_id: string
  probe_at: string
  support: CredentialProbeSupport
  upstream: CredentialProbeUpstream
  items: CredentialUpstreamItem[]
  message?: string | null
  http_status?: number | null
}

export interface PersonalModelBatchImportBody {
  provider: string
  upstream_model_ids: string[]
  model_types: string[]
  display_name_prefix?: string | null
  enabled?: boolean
  tags?: Record<string, unknown> | null
}

export interface PersonalModelBatchImportCreatedItem {
  upstream_model_id: string
  gateway_model_ids: string[]
}

export interface BatchImportFailureItem {
  upstream_model_id: string
  reason: string
}

export interface PersonalModelBatchImportResponse {
  credential_id: string
  created: PersonalModelBatchImportCreatedItem[]
  failed: BatchImportFailureItem[]
}

export interface TeamGatewayModelBatchImportItem {
  upstream_model_id: string
  name?: string | null
}

export interface TeamGatewayModelBatchImportBody {
  provider: string
  capability?: string
  weight?: number
  rpm_limit?: number | null
  tpm_limit?: number | null
  tags?: Record<string, unknown> | null
  enabled?: boolean
  items: TeamGatewayModelBatchImportItem[]
}

export interface TeamGatewayModelBatchImportCreatedItem {
  upstream_model_id: string
  gateway_model_id: string
}

export interface TeamGatewayModelBatchImportResponse {
  credential_id: string
  created: TeamGatewayModelBatchImportCreatedItem[]
  failed: BatchImportFailureItem[]
}

export interface PersonalGatewayModelUpdateBody {
  display_name?: string
  model_id?: string
  credential_id?: string
  is_active?: boolean
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
  model_types?: string[]
  selector_capabilities?: Record<string, unknown>
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
  enabled?: boolean
}

/** PATCH /models/{id}，与 GatewayModelUpdate 对齐 */
export interface GatewayModelUpdateBody {
  name?: string | null
  real_model?: string | null
  credential_id?: string | null
  weight?: number | null
  rpm_limit?: number | null
  tpm_limit?: number | null
  enabled?: boolean | null
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

/** PATCH /credentials/{id} 与 /my-credentials/{id} 共用字段 */
export interface GatewayCredentialUpdateBody {
  name?: string | null
  api_key?: string | null
  api_base?: string | null
  extra?: Record<string, unknown> | null
  is_active?: boolean | null
}

export interface GatewayBudget {
  id: string
  scope: 'system' | 'team' | 'key' | 'user'
  scope_id: string | null
  period: 'daily' | 'monthly' | 'total'
  model_name: string | null
  limit_usd: number | null
  soft_limit_usd?: number | null
  limit_tokens: number | null
  limit_requests: number | null
  current_usd: number
  current_tokens: number
  current_requests: number
  reset_at: string | null
  budget_reset_at?: string | null
}

/** PUT /budgets 请求体（与 BudgetUpsert 一致） */
export interface BudgetUpsertBody {
  scope: 'system' | 'team' | 'key' | 'user'
  scope_id?: string | null
  period: 'daily' | 'monthly' | 'total'
  model_name?: string | null
  limit_usd?: number | null
  soft_limit_usd?: number | null
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
 * - workspace（产品文案：团队）：按当前 X-Team-Id 选中的团队（含 personal/shared）过滤/聚合。
 * - user（产品文案：我）：按当前登录账号跨团队聚合。
 *
 * 字面量保留 `workspace` 是为了与 BudgetScope.team 字面量正交，避免 URL/JSON 中误读。
 */
export type GatewayUsageAggregation = 'workspace' | 'user'

export interface GatewayLogItem {
  id: string
  created_at: string
  team_id: string | null
  user_id: string | null
  vkey_id: string | null
  credential_id: string | null
  credential_name_snapshot: string | null
  /** Router 选中的注册模型 id；与 route_name（客户端 model）可不同 */
  deployment_gateway_model_id?: string | null
  deployment_model_name?: string | null
  capability: string
  route_name: string | null
  real_model: string | null
  provider: string | null
  status: string
  error_code: string | null
  error_message?: string | null
  input_tokens: number
  output_tokens: number
  cached_tokens: number
  cost_usd: number | string
  revenue_usd?: number | string
  latency_ms: number
  ttfb_ms?: number | null
  cache_hit: boolean
  fallback_chain: string[]
  request_id: string | null
  prompt_hash?: string | null
  user_email_snapshot: string | null
  vkey_name_snapshot: string | null
}

/** GET /logs/{id}，含脱敏 prompt / 响应摘要等 */
export interface GatewayLogDetail extends GatewayLogItem {
  team_snapshot?: Record<string, unknown> | null
  route_snapshot?: Record<string, unknown> | null
  prompt_redacted?: Record<string, unknown> | null
  response_summary?: Record<string, unknown> | null
  metadata_extra?: Record<string, unknown> | null
  pricing_snapshot?: Record<string, unknown> | null
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
// Provider / Entitlement Plans（与 backend schemas 对齐）
// ============================

export type PlanResetStrategy =
  | 'rolling'
  | 'calendar_daily_utc'
  | 'calendar_monthly_utc'
  | 'plan_anniversary'

export interface PlanQuotaInput {
  label: string
  window_seconds: number
  reset_strategy?: PlanResetStrategy
  limit_usd?: number | string | null
  limit_tokens?: number | null
  limit_requests?: number | null
}

export interface EntitlementPlanQuotaInput extends PlanQuotaInput {
  unit_price_usd_per_token?: number | string | null
  unit_price_usd_per_request?: number | string | null
}

export interface PlanQuota {
  id: string
  label: string
  window_seconds: number
  reset_strategy: PlanResetStrategy
  limit_usd: number | string | null
  limit_tokens: number | null
  limit_requests: number | null
}

export interface EntitlementPlanQuota extends PlanQuota {
  unit_price_usd_per_token?: number | string | null
  unit_price_usd_per_request?: number | string | null
}

export interface ProviderPlan {
  id: string
  credential_id: string
  real_model: string | null
  label: string
  valid_from: string
  valid_until: string
  is_active: boolean
  auto_renew: boolean
  notes: string | null
  extra: Record<string, unknown> | null
  quotas: PlanQuota[]
}

export interface ProviderPlanCreateBody {
  real_model?: string | null
  label: string
  valid_from: string
  valid_until: string
  is_active?: boolean
  auto_renew?: boolean
  notes?: string | null
  extra?: Record<string, unknown> | null
  quotas?: PlanQuotaInput[]
}

export interface ProviderPlanUpdateBody {
  real_model?: string | null
  label?: string
  valid_from?: string
  valid_until?: string
  is_active?: boolean
  auto_renew?: boolean
  notes?: string | null
  extra?: Record<string, unknown> | null
  quotas?: PlanQuotaInput[]
}

export interface EntitlementPlan {
  id: string
  scope: 'vkey' | 'apikey_grant'
  scope_id: string
  label: string
  valid_from: string
  valid_until: string
  included_models: string[]
  included_capabilities: string[]
  is_active: boolean
  auto_renew: boolean
  notes: string | null
  extra: Record<string, unknown> | null
  quotas: EntitlementPlanQuota[]
}

export interface EntitlementPlanCreateBody {
  label: string
  valid_from: string
  valid_until: string
  included_models?: string[]
  included_capabilities?: string[]
  is_active?: boolean
  auto_renew?: boolean
  notes?: string | null
  extra?: Record<string, unknown> | null
  quotas?: EntitlementPlanQuotaInput[]
}

export interface EntitlementPlanUpdateBody {
  label?: string
  valid_from?: string
  valid_until?: string
  included_models?: string[]
  included_capabilities?: string[]
  is_active?: boolean
  auto_renew?: boolean
  notes?: string | null
  extra?: Record<string, unknown> | null
  quotas?: EntitlementPlanQuotaInput[]
}

export interface EntitlementUsage {
  plan_id: string
  period_start: string
  period_end: string
  requests: number
  input_tokens: number
  output_tokens: number
  cost_usd: number | string
  charged_usd: number | string
}

export interface ProviderPlanCost {
  plan_id: string
  period_start: string
  period_end: string
  requests: number
  input_tokens: number
  output_tokens: number
  cost_usd: number | string
}

export interface MarginGroupItem {
  group_key: string
  label: string
  revenue_usd: number | string
  cost_usd: number | string
  margin_usd: number | string
  margin_ratio: number
}

export type MarginGroupBy = 'credential' | 'model' | 'team'

export interface MarginSummary {
  period_start: string
  period_end: string
  total_revenue_usd: number | string
  total_cost_usd: number | string
  total_margin_usd: number | string
  group_by: MarginGroupBy
  group_column_label: string
  items: MarginGroupItem[]
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
  revokeKeysBatch: (keyIds: string[]) =>
    apiClient.post<VirtualKeyBatchRevokeResult>(`${base}/keys/revoke-batch`, {
      key_ids: keyIds,
    }),

  listCredentials: () => apiClient.get<ProviderCredential[]>(`${base}/credentials`),
  getCredential: (id: string) => apiClient.get<ProviderCredential>(`${base}/credentials/${id}`),
  revealCredential: (id: string) =>
    apiClient.get<{ api_key: string }>(`${base}/credentials/${id}/reveal`),
  createCredential: (body: {
    provider: string
    name: string
    api_key: string
    api_base?: string
    extra?: Record<string, unknown>
    /** 默认 team；system 仅平台管理员可创建 */
    scope?: 'team' | 'system'
  }) => apiClient.post<ProviderCredential>(`${base}/credentials`, body),
  updateCredential: (id: string, body: GatewayCredentialUpdateBody) =>
    apiClient.patch<ProviderCredential>(`${base}/credentials/${id}`, body),
  deleteCredential: (id: string) => apiClient.delete<unknown>(`${base}/credentials/${id}`),

  listMyCredentials: () => apiClient.get<ProviderCredential[]>(`${base}/my-credentials`),
  revealMyCredential: (id: string) =>
    apiClient.get<{ api_key: string }>(`${base}/my-credentials/${id}/reveal`),
  createMyCredential: (body: {
    provider: string
    name: string
    api_key: string
    api_base?: string | null
    extra?: Record<string, unknown>
  }) => apiClient.post<ProviderCredential>(`${base}/my-credentials`, body),
  updateMyCredential: (id: string, body: GatewayCredentialUpdateBody) =>
    apiClient.patch<ProviderCredential>(`${base}/my-credentials/${id}`, body),
  deleteMyCredential: (id: string) => apiClient.delete<unknown>(`${base}/my-credentials/${id}`),

  probeMyCredential: (credentialId: string) =>
    apiClient.post<CredentialProbeResult>(`${base}/my-credentials/${credentialId}/probe`, {}),
  batchImportMyModelsFromUpstream: (credentialId: string, body: PersonalModelBatchImportBody) =>
    apiClient.post<PersonalModelBatchImportResponse>(
      `${base}/my-credentials/${credentialId}/batch-import-models`,
      body
    ),

  probeTeamCredential: (credentialId: string) =>
    apiClient.post<CredentialProbeResult>(`${base}/credentials/${credentialId}/probe`, {}),
  batchImportTeamModelsFromUpstream: (
    credentialId: string,
    body: TeamGatewayModelBatchImportBody
  ) =>
    apiClient.post<TeamGatewayModelBatchImportResponse>(
      `${base}/credentials/${credentialId}/batch-import-models`,
      body
    ),

  listMyModels: (params?: { provider?: string }) =>
    apiClient.get<PersonalGatewayModel[]>(`${base}/my-models`, params),
  createMyModel: (body: PersonalGatewayModelCreateBody) =>
    apiClient.post<PersonalGatewayModel[]>(`${base}/my-models`, body),
  updateMyModel: (id: string, body: PersonalGatewayModelUpdateBody) =>
    apiClient.patch<PersonalGatewayModel>(`${base}/my-models/${id}`, body),
  deleteMyModel: (id: string) => apiClient.delete<unknown>(`${base}/my-models/${id}`),
  testMyModel: (id: string) =>
    apiClient.post<GatewayModelTestResult>(`${base}/my-models/${id}/test`, {}),

  listAvailableModels: (
    type?: ModelType,
    provider?: string,
    options?: { mode?: 'chat' | 'image_gen' | 'video' }
  ) => {
    const search: Record<string, string> = {}
    if (type) search.type = type
    if (provider) search.provider = provider
    if (options?.mode) search.mode = options.mode
    return apiClient.get<AvailableModelsResponse>(`${base}/models/available`, search)
  },

  listModels: (params?: { provider?: string; credential_id?: string }) =>
    apiClient.get<GatewayModel[]>(`${base}/models`, params),
  modelsUsageSummary: (params?: { days?: number; provider?: string }) =>
    apiClient.get<GatewayModelUsageSummary>(`${base}/models/usage-summary`, params),
  adminCredentialStats: (params?: { days?: number }) =>
    apiClient.get<PlatformCredentialStat[]>(`${base}/admin/credential-stats`, params),
  listModelPresets: (params?: { provider?: string }) =>
    apiClient.get<GatewayModelPreset[]>(`${base}/models/presets`, params),
  createModel: (body: GatewayModelCreateBody) =>
    apiClient.post<GatewayModel>(`${base}/models`, body),
  updateModel: (id: string, body: GatewayModelUpdateBody) =>
    apiClient.patch<GatewayModel>(`${base}/models/${id}`, body),
  deleteModel: (id: string) => apiClient.delete<unknown>(`${base}/models/${id}`),
  /** 对一条 Gateway 团队模型发起最小 LLM 调用，结果同步落到 last_test_status / last_tested_at */
  testModel: (id: string) =>
    apiClient.post<GatewayModelTestResult>(`${base}/models/${id}/test`, {}),

  listRoutes: () => apiClient.get<GatewayRoute[]>(`${base}/routes`),
  createRoute: (body: GatewayRouteCreateBody) =>
    apiClient.post<GatewayRoute>(`${base}/routes`, body),
  updateRoute: (id: string, body: GatewayRouteUpdateBody) =>
    apiClient.patch<GatewayRoute>(`${base}/routes/${id}`, body),
  deleteRoute: (id: string) => apiClient.delete<unknown>(`${base}/routes/${id}`),

  listBudgets: () => apiClient.get<GatewayBudget[]>(`${base}/budgets`),
  upsertBudget: (body: BudgetUpsertBody) => apiClient.put<GatewayBudget>(`${base}/budgets`, body),
  deleteBudget: (id: string) => apiClient.delete<unknown>(`${base}/budgets/${id}`),

  listLogs: (params?: {
    /** 默认 workspace（产品文案：团队） */
    usage_aggregation?: GatewayUsageAggregation
    page?: number
    page_size?: number
    capability?: string
    status?: string
    start?: string
    end?: string
    vkey_id?: string
    credential_id?: string
  }) =>
    apiClient.get<{
      items: GatewayLogItem[]
      total: number
      page: number
      page_size: number
    }>(`${base}/logs`, params),
  getLog: (id: string, params?: { usage_aggregation?: GatewayUsageAggregation }) =>
    apiClient.get<GatewayLogDetail>(`${base}/logs/${id}`, params),

  dashboard: (params?: { days?: number; usage_aggregation?: GatewayUsageAggregation }) =>
    apiClient.get<DashboardSummary>(`${base}/dashboard/summary`, params),

  listAlerts: () => apiClient.get<AlertRule[]>(`${base}/alerts/rules`),
  createAlert: (body: AlertRuleCreateBody) =>
    apiClient.post<AlertRule>(`${base}/alerts/rules`, body),
  deleteAlert: (id: string) => apiClient.delete<unknown>(`${base}/alerts/rules/${id}`),

  importFromUserConfig: () => apiClient.post<{ created: number }>(`${base}/credentials/import`),

  // ============================
  // Provider / Entitlement Plans
  // ============================
  listProviderPlans: (credentialId: string) =>
    apiClient.get<ProviderPlan[]>(`${base}/credentials/${credentialId}/provider-plans`),
  createProviderPlan: (credentialId: string, body: ProviderPlanCreateBody) =>
    apiClient.post<ProviderPlan>(`${base}/credentials/${credentialId}/provider-plans`, body),
  updateProviderPlan: (credentialId: string, planId: string, body: ProviderPlanUpdateBody) =>
    apiClient.patch<ProviderPlan>(
      `${base}/credentials/${credentialId}/provider-plans/${planId}`,
      body
    ),
  deleteProviderPlan: (credentialId: string, planId: string) =>
    apiClient.delete<unknown>(`${base}/credentials/${credentialId}/provider-plans/${planId}`),
  listProviderPlanUsage: (credentialId: string, params?: { days?: number }) =>
    apiClient.get<ProviderPlanCost[]>(
      `${base}/credentials/${credentialId}/provider-plan-usage`,
      params
    ),

  listVkeyEntitlements: (vkeyId: string) =>
    apiClient.get<EntitlementPlan[]>(`${base}/keys/${vkeyId}/entitlements`),
  createVkeyEntitlement: (vkeyId: string, body: EntitlementPlanCreateBody) =>
    apiClient.post<EntitlementPlan>(`${base}/keys/${vkeyId}/entitlements`, body),
  listGrantEntitlements: (grantId: string) =>
    apiClient.get<EntitlementPlan[]>(`${base}/api-key-grants/${grantId}/entitlements`),
  createGrantEntitlement: (grantId: string, body: EntitlementPlanCreateBody) =>
    apiClient.post<EntitlementPlan>(`${base}/api-key-grants/${grantId}/entitlements`, body),
  updateEntitlementPlan: (planId: string, body: EntitlementPlanUpdateBody) =>
    apiClient.patch<EntitlementPlan>(`${base}/entitlements/${planId}`, body),
  deleteEntitlementPlan: (planId: string) =>
    apiClient.delete<unknown>(`${base}/entitlements/${planId}`),
  getEntitlementUsage: (planId: string, params?: { days?: number }) =>
    apiClient.get<EntitlementUsage>(`${base}/entitlements/${planId}/usage`, params),

  dashboardMargin: (params?: { days?: number; group_by?: 'credential' | 'model' | 'team' }) =>
    apiClient.get<MarginSummary>(`${base}/dashboard/margin`, params),

  // Pricing catalog
  getFxRates: () =>
    apiClient.get<{ usd_cny: string; adapter: string; default_display_currency: string }>(
      `${base}/pricing/fx`
    ),
  listUpstreamPricing: (params?: { provider?: string; currency?: DisplayCurrency }) =>
    apiClient.get<UpstreamPricingRow[]>(`${base}/pricing/upstream`, params),
  createUpstreamPricing: (body: UpstreamPricingUpsertBody) =>
    apiClient.post<UpstreamPricingRow>(`${base}/pricing/upstream`, body),
  listDownstreamPricing: (params?: {
    scope?: 'global' | 'team' | 'entitlement_plan'
    scope_id?: string
    currency?: DisplayCurrency
  }) => apiClient.get<DownstreamPricingRow[]>(`${base}/pricing/downstream`, params),
  createDownstreamPricing: (body: DownstreamPricingUpsertBody) =>
    apiClient.post<DownstreamPricingRow>(`${base}/pricing/downstream`, body),
  syncDownstreamPricing: (params?: { scope?: 'team' | 'entitlement_plan'; scope_id?: string }) => {
    const qs = new URLSearchParams()
    if (params?.scope) qs.set('scope', params.scope)
    if (params?.scope_id) qs.set('scope_id', params.scope_id)
    const q = qs.toString()
    return apiClient.post<{ created: number; skipped: number }>(
      `${base}/pricing/downstream/sync${q ? `?${q}` : ''}`,
      {}
    )
  },
  listMyPrices: (params?: { currency?: DisplayCurrency }) =>
    apiClient.get<MyPriceRow[]>(`${base}/pricing/my`, params),
  auditUpstreamPricing: () =>
    apiClient.get<UpstreamPricingAuditResult>(`${base}/pricing/upstream/audit`),
  syncUpstreamFromLitellm: () =>
    apiClient.post<LitellmUpstreamSyncResult>(`${base}/pricing/upstream/sync-from-litellm`, {}),
  estimatePricing: (body: PricingEstimateBody) =>
    apiClient.post<PricingEstimateResult>(`${base}/pricing/estimate`, body),
  pricingReconciliation: (params: { year: number; month: number }) =>
    apiClient.get<PricingReconciliationResult>(`${base}/pricing/reconciliation`, params),
}

export interface UpstreamPricingRow {
  id: string
  provider: string
  upstream_model: string
  capability: string
  input_cost_per_token_usd: string
  output_cost_per_token_usd: string
  input_cost_per_million_display?: MoneyDisplay | null
  output_cost_per_million_display?: MoneyDisplay | null
  effective_from: string
  effective_to: string | null
  version: number
  source: string
  display_currency?: string
  fx_rate_used?: string
}

export interface UpstreamPricingUpsertBody {
  provider: string
  upstream_model: string
  capability?: string
  currency?: DisplayCurrency
  amount_per_million: Record<string, number | null>
}

export interface DownstreamPricingRow {
  id: string
  scope: string
  scope_id: string | null
  gateway_model_id: string | null
  inheritance_strategy: string
  input_cost_per_token_usd?: string | null
  output_cost_per_token_usd?: string | null
  input_cost_per_million_display?: MoneyDisplay | null
  output_cost_per_million_display?: MoneyDisplay | null
  effective_from: string
  effective_to: string | null
  version: number
}

export interface DownstreamPricingUpsertBody {
  scope: 'global' | 'team' | 'entitlement_plan'
  scope_id?: string | null
  gateway_model_id?: string | null
  inheritance_strategy?: 'mirror' | 'manual'
  currency?: DisplayCurrency
  amount_per_million?: Record<string, number | null> | null
}

export interface MyPriceRow {
  gateway_model_id: string | null
  model_name: string | null
  input_cost_per_million_display?: MoneyDisplay | null
  output_cost_per_million_display?: MoneyDisplay | null
  inheritance_strategy?: string | null
  display_currency: string
}

export interface UpstreamPricingAuditResult {
  models_without_upstream: string[]
  upstream_without_model: string[]
  registered_upstream_keys: number
}

export interface LitellmUpstreamSyncResult {
  created: number
  updated: number
  skipped_manual: number
}

export interface PricingEstimateBody {
  gateway_model_id: string
  input_tokens?: number
  output_tokens?: number
  cache_read_tokens?: number
}

export interface PricingEstimateResult {
  gateway_model_id: string
  hit_chain: string[]
  upstream_cost_usd: string
  downstream_revenue_usd: string
  margin_usd: string
  rate_snapshot: Record<string, unknown>
  disclaimer: string
}

export interface PricingReconciliationResult {
  team_id: string
  period: string
  requests: number
  cost_usd: string
  revenue_usd: string
  margin_usd: string
  top_models: Array<{
    route_name: string | null
    requests: number
    cost_usd: string
    revenue_usd: string
    margin_usd: string
  }>
}
