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
  current_usd: number
  current_tokens: number
  current_requests: number
  reset_at: string | null
  budget_reset_at: string | null
}

export interface QuotaRule {
  key: QuotaRuleKey
  source_ref: QuotaRuleSourceRef
  limits: QuotaRuleLimits
  usage: QuotaRuleUsage | null
  plan_label: string | null
  is_active: boolean
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
  plan_label?: string | null
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
}

export const quotaRulesApi = {
  listQuotaRules: (teamId: string, params?: ListQuotaRulesParams) => {
    const search = new URLSearchParams()
    if (params?.layer) search.set('layer', params.layer)
    if (params?.user_id) search.set('user_id', params.user_id)
    if (params?.credential_id) search.set('credential_id', params.credential_id)
    if (params?.model_name) search.set('model_name', params.model_name)
    if (params?.period) search.set('period', params.period)
    const qs = search.toString()
    const path = qs ? `/quota-rules?${qs}` : '/quota-rules'
    return apiClient.get<QuotaRule[]>(teamGatewayPath(teamId, path))
  },
  batchUpsertQuotaRules: (teamId: string, rules: QuotaRuleUpsertBody[]) =>
    apiClient.put<QuotaRuleBatchUpsertResponse>(teamGatewayPath(teamId, '/quota-rules/batch'), {
      rules,
    }),
} as const
