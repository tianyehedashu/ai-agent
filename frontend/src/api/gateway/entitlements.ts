/**
 * AI Gateway · 下游权益套餐与利润
 *
 * Entitlement Plan：下游客户套餐（绑定 vkey 或 api-key-grant），表达「我们卖给客户多少」。
 * 利润（margin）= 下游 revenue − 上游 cost；按 credential / model / team 分组聚合。
 */

import { apiClient } from '@/api/client'

import { teamGatewayPath } from './_base'

// ---------- 配额公共类型 ----------

export type PlanResetStrategy = 'rolling' | 'calendar_daily_utc' | 'calendar_monthly_utc'
/** 套餐配额输入 */
export interface PlanQuotaInput {
  label: string
  window_seconds: number
  reset_strategy?: PlanResetStrategy
  limit_usd?: number | string | null
  limit_tokens?: number | null
  limit_requests?: number | null
  reset_timezone?: string | null
  reset_time_minutes?: number | null
  reset_day_of_month?: number | null
}

/** Entitlement Plan 配额输入（额外携带单价信息） */
export interface EntitlementPlanQuotaInput extends PlanQuotaInput {
  unit_price_usd_per_token?: number | string | null
  unit_price_usd_per_request?: number | string | null
}

/** 套餐配额读模型 */
export interface PlanQuota {
  id: string
  label: string
  window_seconds: number
  reset_strategy: PlanResetStrategy
  limit_usd: number | string | null
  limit_tokens: number | null
  limit_requests: number | null
  reset_timezone: string
  reset_time_minutes: number
  reset_day_of_month: number
}

/** Entitlement Plan 配额读模型（含单价） */
export interface EntitlementPlanQuota extends PlanQuota {
  unit_price_usd_per_token?: number | string | null
  unit_price_usd_per_request?: number | string | null
}

// ---------- Entitlement Plan（下游客户套餐） ----------

export interface EntitlementPlan {
  id: string
  /** vkey：绑定虚拟 Key；apikey_grant：绑定 API Key 授权链 */
  scope: 'vkey' | 'apikey_grant'
  scope_id: string
  label: string
  valid_from: string
  included_models: string[]
  included_capabilities: string[]
  notes: string | null
  extra: Record<string, unknown> | null
  quotas: EntitlementPlanQuota[]
}

export interface EntitlementPlanCreateBody {
  label: string
  valid_from: string
  included_models?: string[]
  included_capabilities?: string[]
  notes?: string | null
  extra?: Record<string, unknown> | null
  quotas?: EntitlementPlanQuotaInput[]
}

export interface EntitlementPlanUpdateBody {
  label?: string
  valid_from?: string
  included_models?: string[]
  included_capabilities?: string[]
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

/** Entitlements / Margin 资源 API */
export const entitlementsApi = {
  // --- Entitlement Plan ---
  /** 列出虚拟 Key 绑定的下游客户套餐 */
  listVkeyEntitlements: (teamId: string, vkeyId: string) =>
    apiClient.get<EntitlementPlan[]>(teamGatewayPath(teamId, `/keys/${vkeyId}/entitlements`)),
  createVkeyEntitlement: (teamId: string, vkeyId: string, body: EntitlementPlanCreateBody) =>
    apiClient.post<EntitlementPlan>(teamGatewayPath(teamId, `/keys/${vkeyId}/entitlements`), body),
  /** 列出 API Key 授权链绑定的下游客户套餐 */
  listGrantEntitlements: (teamId: string, grantId: string) =>
    apiClient.get<EntitlementPlan[]>(
      teamGatewayPath(teamId, `/api-key-grants/${grantId}/entitlements`)
    ),
  createGrantEntitlement: (teamId: string, grantId: string, body: EntitlementPlanCreateBody) =>
    apiClient.post<EntitlementPlan>(
      teamGatewayPath(teamId, `/api-key-grants/${grantId}/entitlements`),
      body
    ),
  updateEntitlementPlan: (teamId: string, planId: string, body: EntitlementPlanUpdateBody) =>
    apiClient.patch<EntitlementPlan>(teamGatewayPath(teamId, `/entitlements/${planId}`), body),
  deleteEntitlementPlan: (teamId: string, planId: string) =>
    apiClient.delete<unknown>(teamGatewayPath(teamId, `/entitlements/${planId}`)),
  /** 下游客户套餐用量（结算口径） */
  getEntitlementUsage: (teamId: string, planId: string, params?: { days?: number }) =>
    apiClient.get<EntitlementUsage>(
      teamGatewayPath(teamId, `/entitlements/${planId}/usage`),
      params
    ),

  // --- Margin（利润大盘） ---
  /** 利润聚合（按 credential / model / team 分组） */
  dashboardMargin: (teamId: string, params?: { days?: number; group_by?: MarginGroupBy }) =>
    apiClient.get<MarginSummary>(teamGatewayPath(teamId, '/dashboard/margin'), params),
} as const
