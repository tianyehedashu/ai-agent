/**
 * AI Gateway · 计价目录（Pricing Catalog）
 *
 * 三层计价：
 * - 上游计价（Upstream）：成本侧，由 LiteLLM 价格表或手动维护
 * - 下游计价（Downstream）：收入侧，按 global / team / entitlement_plan 三种作用域
 * - 我的计价（My Prices）：当前调用方实际能看到的「单价 + 货币 + 继承策略」聚合视图
 *
 * 此外提供 FX 汇率、对账（reconciliation）、单次调用估价（estimate）、上游同步等运维端点。
 */

import { apiClient } from '@/api/client'
import type { DisplayCurrency, MoneyDisplay } from '@/types/money'

import { teamGatewayPath } from './_base'

/** GET /pricing/fx 汇率与适配器信息 */
export interface FxRateInfo {
  usd_cny: string
  adapter: string
  default_display_currency: string
}

// ---------- 上游计价 ----------

export interface UpstreamPricingRow {
  id: string
  provider: string
  upstream_model: string
  capability: string
  input_cost_per_token_usd: string
  output_cost_per_token_usd: string
  input_cost_per_million_display?: MoneyDisplay | null
  output_cost_per_million_display?: MoneyDisplay | null
  cache_creation_input_token_cost_usd?: string | null
  cache_read_input_token_cost_usd?: string | null
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
  /** 单位：每百万 token 单价（keys 同 backend `amount_per_million` 字段） */
  amount_per_million: Record<string, number | null>
}

// ---------- 下游计价 ----------

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
  scope: 'global' | 'tenant' | 'entitlement_plan'
  scope_id?: string | null
  gateway_model_id?: string | null
  /** mirror：继承上游；manual：使用本行 amount_per_million */
  inheritance_strategy?: 'mirror' | 'manual'
  currency?: DisplayCurrency
  amount_per_million?: Record<string, number | null> | null
}

// ---------- 我的计价（聚合视图） ----------

export interface MyPriceRow {
  gateway_model_id: string | null
  model_name: string | null
  input_cost_per_million_display?: MoneyDisplay | null
  output_cost_per_million_display?: MoneyDisplay | null
  inheritance_strategy?: string | null
  display_currency: string
}

// ---------- 审计 / 同步 / 估价 / 对账 ----------

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

export interface EffectiveProvider {
  provider: string
  credential_count: number
  has_managed: boolean
  has_user: boolean
}

export interface LitellmUpstreamSyncBody {
  providers?: string[] | null
}

export interface PricingEstimateBody {
  gateway_model_id: string
  input_tokens?: number
  output_tokens?: number
  cache_read_tokens?: number
}

export interface PricingEstimateResult {
  gateway_model_id: string
  /** 命中规则的链路（按优先级从高到低） */
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

/** Pricing 资源 API */
export const pricingApi = {
  /** 获取当前 FX 汇率与适配器信息（首屏货币切换依赖） */
  getFxRates: (teamId: string) => apiClient.get<FxRateInfo>(teamGatewayPath(teamId, '/pricing/fx')),

  // --- 上游计价 ---
  /** 列出实际已配置凭据的 provider，用作上游同步白名单 */
  getEffectiveProviders: (teamId: string) =>
    apiClient.get<EffectiveProvider[]>(teamGatewayPath(teamId, '/pricing/effective-providers')),
  /** 列出上游计价（按 provider / currency 过滤） */
  listUpstreamPricing: (
    teamId: string,
    params?: { provider?: string; currency?: DisplayCurrency }
  ) => apiClient.get<UpstreamPricingRow[]>(teamGatewayPath(teamId, '/pricing/upstream'), params),
  /** 新增 / 更新一条上游计价（增量版本，旧版自动 effective_to 截断） */
  createUpstreamPricing: (teamId: string, body: UpstreamPricingUpsertBody) =>
    apiClient.post<UpstreamPricingRow>(teamGatewayPath(teamId, '/pricing/upstream'), body),
  /** 审计：列出缺失或多余的上游计价键 */
  auditUpstreamPricing: (teamId: string) =>
    apiClient.get<UpstreamPricingAuditResult>(teamGatewayPath(teamId, '/pricing/upstream/audit')),
  /** 从 LiteLLM 价格表同步上游计价（manual 行不会被覆盖） */
  syncUpstreamFromLitellm: (teamId: string, body?: LitellmUpstreamSyncBody) =>
    apiClient.post<LitellmUpstreamSyncResult>(
      teamGatewayPath(teamId, '/pricing/upstream/sync-from-litellm'),
      body ?? {}
    ),

  // --- 下游计价 ---
  /** 列出下游计价（按 scope / scope_id / currency 过滤） */
  listDownstreamPricing: (
    teamId: string,
    params?: {
      scope?: 'global' | 'tenant' | 'entitlement_plan'
      scope_id?: string
      currency?: DisplayCurrency
    }
  ) =>
    apiClient.get<DownstreamPricingRow[]>(teamGatewayPath(teamId, '/pricing/downstream'), params),
  /** 新增 / 更新一条下游计价 */
  createDownstreamPricing: (teamId: string, body: DownstreamPricingUpsertBody) =>
    apiClient.post<DownstreamPricingRow>(teamGatewayPath(teamId, '/pricing/downstream'), body),
  /**
   * 从上游同步下游计价（mirror 策略）。
   * - scope/scope_id 缺省时仅同步 global
   * - 返回新建条数与因冲突跳过的条数
   */
  syncDownstreamPricing: (
    teamId: string,
    params?: {
      scope?: 'tenant' | 'entitlement_plan'
      scope_id?: string
    }
  ) => {
    const qs = new URLSearchParams()
    if (params?.scope) qs.set('scope', params.scope)
    if (params?.scope_id) qs.set('scope_id', params.scope_id)
    const q = qs.toString()
    return apiClient.post<{ created: number; skipped: number }>(
      `${teamGatewayPath(teamId, '/pricing/downstream/sync')}${q ? `?${q}` : ''}`,
      {}
    )
  },

  // --- 我的计价 / 单次估价 / 对账 ---
  /** 当前调用方可见的「单价 + 货币 + 继承策略」聚合视图 */
  listMyPrices: (teamId: string, params?: { currency?: DisplayCurrency }) =>
    apiClient.get<MyPriceRow[]>(teamGatewayPath(teamId, '/pricing/my'), params),
  /** 单次调用估价（基于命中链路的 cost / revenue / margin） */
  estimatePricing: (teamId: string, body: PricingEstimateBody) =>
    apiClient.post<PricingEstimateResult>(teamGatewayPath(teamId, '/pricing/estimate'), body),
  /** 月度对账（团队维度，cost / revenue / margin / top models） */
  pricingReconciliation: (teamId: string, params: { year: number; month: number }) =>
    apiClient.get<PricingReconciliationResult>(
      teamGatewayPath(teamId, '/pricing/reconciliation'),
      params
    ),
} as const
