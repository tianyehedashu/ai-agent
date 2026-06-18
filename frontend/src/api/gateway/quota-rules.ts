/**
 * AI Gateway · 统一配额规则（Quota Rules）
 */

import { apiClient } from '@/api/client'

import { teamGatewayPath } from './_base'

export type QuotaRuleLayer = 'platform' | 'upstream' | 'downstream'
export type QuotaRuleAccessKind = 'none' | 'vkey' | 'apikey_grant'

export interface QuotaRuleKey {
  team_id: string
  layer: QuotaRuleLayer
  user_id: string | null
  credential_id: string | null
  model_name: string | null
  period: string | null
  window_seconds: number | null
  reset_strategy: string | null
  period_timezone?: string | null
  period_reset_minutes?: number | null
  period_reset_day?: number | null
  access_kind: QuotaRuleAccessKind
  access_id: string | null
  quota_label: string | null
  target_kind: string | null
  target_id: string | null
}

export interface QuotaRuleSourceRef {
  layer: QuotaRuleLayer
  budget_id: string | null
  plan_id: string | null
  quota_id: string | null
}

export interface QuotaRuleLimits {
  limit_usd: number | null
  soft_limit_usd: number | null
  limit_tokens: number | null
  limit_requests: number | null
  unit_price_usd_per_token: number | null
  unit_price_usd_per_request: number | null
}

export interface QuotaRuleUsage {
  current_usd: number | null
  current_tokens: number | null
  current_requests: number | null
  window_start: string | null
  reset_at: string | null
  budget_reset_at: string | null
}

export interface QuotaRule {
  key: QuotaRuleKey
  source_ref: QuotaRuleSourceRef
  limits: QuotaRuleLimits
  usage: QuotaRuleUsage | null
  /** @deprecated 上游已拍平为 key.quota_label；下游可能仍返回 plan_label */
  plan_label?: string | null
  /** 启用停用：false 时该规则不参与热路径执法 */
  is_active: boolean
  /** 起止时间（含/不含）；null 表示该侧不限 */
  valid_from: string | null
  valid_until: string | null
}

/** 下游兼容：读取可能仍返回的 plan_label（避免在 UI 层直接访问 deprecated 字段） */
export function quotaRuleLegacyPlanLabel(rule: QuotaRule): string | null {
  const trimmed = (rule as { plan_label?: string | null }).plan_label?.trim()
  if (!trimmed) return null
  return trimmed
}

export interface QuotaRuleUpsertBody {
  layer: QuotaRuleLayer
  target_kind?: 'system' | 'tenant' | 'key' | 'user' | null
  target_id?: string | null
  user_id?: string | null
  credential_id?: string | null
  model_name?: string | null
  period?: 'daily' | 'monthly' | 'total' | null
  window_seconds?: number | null
  reset_strategy?: string | null
  period_timezone?: string | null
  period_reset_minutes?: number | null
  period_reset_day?: number | null
  reset_timezone?: string | null
  reset_time_minutes?: number | null
  reset_day_of_month?: number | null
  quota_label?: string | null
  access_kind?: QuotaRuleAccessKind
  access_id?: string | null
  included_models?: string[]
  limit_usd?: number | null
  soft_limit_usd?: number | null
  limit_tokens?: number | null
  limit_requests?: number | null
  unit_price_usd_per_token?: number | null
  unit_price_usd_per_request?: number | null
  /** 起止时间（ISO 字符串）；null 表示该侧不限 */
  valid_from?: string | null
  valid_until?: string | null
  /** 启用停用；默认 true */
  enabled?: boolean
}

export interface QuotaRuleBatchFailure {
  index: number
  error: string
}

export interface QuotaRuleBatchUpsertResponse {
  succeeded: QuotaRule[]
  failed: QuotaRuleBatchFailure[]
}

export interface ListQuotaRulesParams {
  layer?: QuotaRuleLayer
  user_id?: string
  credential_id?: string
  model_name?: string
  period?: 'daily' | 'monthly' | 'total'
  include_usage?: boolean
}

export interface QuotaRuleEnablementBody {
  layer: QuotaRuleLayer
  budget_id?: string | null
  plan_id?: string | null
  quota_id?: string | null
  enabled: boolean
}

export type QuotaUsageAdjustmentMode = 'set' | 'reset_window'

export interface QuotaUsageAdjustmentBody {
  layer: QuotaRuleLayer
  budget_id?: string | null
  plan_id?: string | null
  quota_id?: string | null
  mode?: QuotaUsageAdjustmentMode
  current_usd?: number | null
  current_tokens?: number | null
  current_requests?: number | null
}

export const quotaRulesApi = {
  listQuotaRules: (teamId: string, params?: ListQuotaRulesParams) => {
    const search = new URLSearchParams()
    if (params?.layer) search.set('layer', params.layer)
    if (params?.user_id) search.set('user_id', params.user_id)
    if (params?.credential_id) search.set('credential_id', params.credential_id)
    if (params?.model_name) search.set('model_name', params.model_name)
    if (params?.period) search.set('period', params.period)
    if (params?.include_usage) search.set('include_usage', 'true')
    const qs = search.toString()
    const path = qs ? `/quota-rules?${qs}` : '/quota-rules'
    return apiClient.get<QuotaRule[]>(teamGatewayPath(teamId, path))
  },
  batchUpsertQuotaRules: (teamId: string, rules: QuotaRuleUpsertBody[]) =>
    apiClient.put<QuotaRuleBatchUpsertResponse>(teamGatewayPath(teamId, '/quota-rules/batch'), {
      rules,
    }),
  /** 成员自助：仅写本人「user + 本人凭据(+模型)」的平台配额 */
  batchUpsertSelfQuotaRules: (teamId: string, rules: QuotaRuleUpsertBody[]) =>
    apiClient.put<QuotaRuleBatchUpsertResponse>(
      teamGatewayPath(teamId, '/quota-rules/self-batch'),
      { rules }
    ),
  /** 成员自助：删除本人「user + 本人凭据」的平台配额行 */
  deleteSelfQuotaRule: (teamId: string, budgetId: string) =>
    apiClient.delete<unknown>(teamGatewayPath(teamId, `/quota-rules/self/${budgetId}`)),
  /** 团队管理员：删除单条上游 / 下游配额（upstream 仅 quota_id；downstream 需 plan_id） */
  deleteQuotaRule: (
    teamId: string,
    params: { layer: 'upstream' | 'downstream'; quotaId: string; planId?: string }
  ) => {
    const search = new URLSearchParams({
      layer: params.layer,
      quota_id: params.quotaId,
    })
    if (params.planId) search.set('plan_id', params.planId)
    return apiClient.delete<unknown>(
      teamGatewayPath(teamId, `/quota-rules/plan?${search.toString()}`)
    )
  },
  /** 成员自助：删除本人凭据上的单条上游配额 */
  deleteSelfQuotaRuleByQuotaId: (teamId: string, quotaId: string) => {
    const search = new URLSearchParams({ quota_id: quotaId })
    return apiClient.delete<unknown>(
      teamGatewayPath(teamId, `/quota-rules/self/plan?${search.toString()}`)
    )
  },
  adjustQuotaRuleUsage: (teamId: string, body: QuotaUsageAdjustmentBody) =>
    apiClient.post<QuotaRule>(teamGatewayPath(teamId, '/quota-rules/usage-adjustments'), body),
  adjustSelfQuotaRuleUsage: (teamId: string, body: QuotaUsageAdjustmentBody) =>
    apiClient.post<QuotaRule>(teamGatewayPath(teamId, '/quota-rules/self/usage-adjustments'), body),
  /** 团队管理员：启用 / 停用单条配额规则 */
  setQuotaRuleEnablement: (teamId: string, body: QuotaRuleEnablementBody) =>
    apiClient.post<QuotaRule>(teamGatewayPath(teamId, '/quota-rules/enablement'), body),
  /** 成员自助：启用 / 停用本人平台或本人凭据上游配额规则 */
  setSelfQuotaRuleEnablement: (teamId: string, body: QuotaRuleEnablementBody) =>
    apiClient.post<QuotaRule>(teamGatewayPath(teamId, '/quota-rules/self/enablement'), body),
} as const
