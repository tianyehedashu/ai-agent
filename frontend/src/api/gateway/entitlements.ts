/**
 * AI Gateway · 配额套餐与利润
 *
 * 包含两类「套餐」：
 * - Provider Plan：上游供应商套餐（按 `credential_id` 维度持有），表达「我们向上游买了多少」
 * - Entitlement Plan：下游客户套餐（绑定 vkey 或 api-key-grant），表达「我们卖给客户多少」
 *
 * 利润（margin）= 下游 revenue − 上游 cost；同样按 credential / model / team 分组聚合。
 */

import { apiClient } from '@/api/client'

import { GATEWAY_API_BASE } from './_base'

// ---------- 配额公共类型 ----------

export type PlanResetStrategy =
  | 'rolling'
  | 'calendar_daily_utc'
  | 'calendar_monthly_utc'
  | 'plan_anniversary'

/** Provider Plan 配额输入 */
export interface PlanQuotaInput {
  label: string
  window_seconds: number
  reset_strategy?: PlanResetStrategy
  limit_usd?: number | string | null
  limit_tokens?: number | null
  limit_requests?: number | null
}

/** Entitlement Plan 配额输入（额外携带单价信息） */
export interface EntitlementPlanQuotaInput extends PlanQuotaInput {
  unit_price_usd_per_token?: number | string | null
  unit_price_usd_per_request?: number | string | null
}

/** Provider Plan 配额读模型 */
export interface PlanQuota {
  id: string
  label: string
  window_seconds: number
  reset_strategy: PlanResetStrategy
  limit_usd: number | string | null
  limit_tokens: number | null
  limit_requests: number | null
}

/** Entitlement Plan 配额读模型（含单价） */
export interface EntitlementPlanQuota extends PlanQuota {
  unit_price_usd_per_token?: number | string | null
  unit_price_usd_per_request?: number | string | null
}

// ---------- Provider Plan（上游套餐） ----------

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

export interface ProviderPlanCost {
  plan_id: string
  period_start: string
  period_end: string
  requests: number
  input_tokens: number
  output_tokens: number
  cost_usd: number | string
}

// ---------- Entitlement Plan（下游客户套餐） ----------

export interface EntitlementPlan {
  id: string
  /** vkey：绑定虚拟 Key；apikey_grant：绑定 API Key 授权链 */
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
  /** 按套餐结算口径换算后的收入金额 */
  charged_usd: number | string
}

// ---------- Margin（利润聚合） ----------

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

/** Entitlements / Plans / Margin 资源 API */
export const entitlementsApi = {
  // --- Provider Plan ---
  /** 列出某条凭据下的上游供应商套餐 */
  listProviderPlans: (credentialId: string) =>
    apiClient.get<ProviderPlan[]>(`${GATEWAY_API_BASE}/credentials/${credentialId}/provider-plans`),
  createProviderPlan: (credentialId: string, body: ProviderPlanCreateBody) =>
    apiClient.post<ProviderPlan>(
      `${GATEWAY_API_BASE}/credentials/${credentialId}/provider-plans`,
      body
    ),
  updateProviderPlan: (credentialId: string, planId: string, body: ProviderPlanUpdateBody) =>
    apiClient.patch<ProviderPlan>(
      `${GATEWAY_API_BASE}/credentials/${credentialId}/provider-plans/${planId}`,
      body
    ),
  deleteProviderPlan: (credentialId: string, planId: string) =>
    apiClient.delete<unknown>(
      `${GATEWAY_API_BASE}/credentials/${credentialId}/provider-plans/${planId}`
    ),
  /** 上游套餐用量（成本聚合） */
  listProviderPlanUsage: (credentialId: string, params?: { days?: number }) =>
    apiClient.get<ProviderPlanCost[]>(
      `${GATEWAY_API_BASE}/credentials/${credentialId}/provider-plan-usage`,
      params
    ),

  // --- Entitlement Plan ---
  /** 列出虚拟 Key 绑定的下游客户套餐 */
  listVkeyEntitlements: (vkeyId: string) =>
    apiClient.get<EntitlementPlan[]>(`${GATEWAY_API_BASE}/keys/${vkeyId}/entitlements`),
  createVkeyEntitlement: (vkeyId: string, body: EntitlementPlanCreateBody) =>
    apiClient.post<EntitlementPlan>(`${GATEWAY_API_BASE}/keys/${vkeyId}/entitlements`, body),
  /** 列出 API Key 授权链绑定的下游客户套餐 */
  listGrantEntitlements: (grantId: string) =>
    apiClient.get<EntitlementPlan[]>(`${GATEWAY_API_BASE}/api-key-grants/${grantId}/entitlements`),
  createGrantEntitlement: (grantId: string, body: EntitlementPlanCreateBody) =>
    apiClient.post<EntitlementPlan>(
      `${GATEWAY_API_BASE}/api-key-grants/${grantId}/entitlements`,
      body
    ),
  updateEntitlementPlan: (planId: string, body: EntitlementPlanUpdateBody) =>
    apiClient.patch<EntitlementPlan>(`${GATEWAY_API_BASE}/entitlements/${planId}`, body),
  deleteEntitlementPlan: (planId: string) =>
    apiClient.delete<unknown>(`${GATEWAY_API_BASE}/entitlements/${planId}`),
  /** 下游客户套餐用量（结算口径） */
  getEntitlementUsage: (planId: string, params?: { days?: number }) =>
    apiClient.get<EntitlementUsage>(`${GATEWAY_API_BASE}/entitlements/${planId}/usage`, params),

  // --- Margin（利润大盘） ---
  /** 利润聚合（按 credential / model / team 分组） */
  dashboardMargin: (params?: { days?: number; group_by?: MarginGroupBy }) =>
    apiClient.get<MarginSummary>(`${GATEWAY_API_BASE}/dashboard/margin`, params),
} as const
