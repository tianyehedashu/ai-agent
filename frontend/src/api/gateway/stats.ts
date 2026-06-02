/**
 * AI Gateway · 调用统计
 *
 * 团队路径下按调用日志聚合，支持组合筛选与单维度分组。
 */

import { apiClient } from '@/api/client'
import { buildPageQuerySearch } from '@/lib/pagination'
import type { PageQuery, PaginatedList } from '@/types'

import { teamGatewayPath } from './_base'

import type { GatewayUsageAggregation } from './logs'

export type GatewayUsageStatsGroupBy =
  | 'credential'
  | 'user'
  | 'team'
  | 'model'
  | 'vkey'
  | 'provider'
  | 'capability'
  | 'status'
  | 'user_model_credential'

export interface GatewayUsageStatsMetric {
  requests: number
  success_count: number
  failure_count: number
  input_tokens: number
  output_tokens: number
  cached_tokens: number
  total_tokens: number
  cost_usd: number | string
  avg_latency_ms: number
  avg_ttfb_ms: number
  cache_hit_count: number
  success_rate: number
  cache_hit_rate: number
}

export interface GatewayUsageStatsItem extends GatewayUsageStatsMetric {
  group_key: string
  label: string
  group_key_parts?: string[]
  label_parts?: string[]
}

export interface GatewayUsageStatsResponse extends PaginatedList<GatewayUsageStatsItem> {
  start: string
  end: string
  group_by: GatewayUsageStatsGroupBy
  totals: GatewayUsageStatsMetric
}

export type GatewayUsageStatsQuery = PageQuery & {
  days?: number
  usage_aggregation?: GatewayUsageAggregation
  group_by?: GatewayUsageStatsGroupBy
  credential_id?: string
  user_id?: string
  filter_team_id?: string
  model?: string
  provider?: string
  capability?: string
  status?: string
  vkey_id?: string
}

function buildUsageStatsSearch(params?: GatewayUsageStatsQuery): Record<string, string | string[]> {
  const search: Record<string, string | string[]> = buildPageQuerySearch(params)
  if (!params) return search
  if (params.days !== undefined) search.days = String(params.days)
  if (params.usage_aggregation) search.usage_aggregation = params.usage_aggregation
  if (params.group_by) search.group_by = params.group_by
  if (params.credential_id) search.credential_id = params.credential_id
  if (params.user_id) search.user_id = params.user_id
  if (params.filter_team_id) search.filter_team_id = params.filter_team_id
  if (params.model) search.model = params.model
  if (params.provider) search.provider = params.provider
  if (params.capability) search.capability = params.capability
  if (params.status) search.status = params.status
  if (params.vkey_id) search.vkey_id = params.vkey_id
  return search
}

export type UsageStatisticsBreakdownBy = 'credential' | 'model'

export interface UsageStatisticsBreakdownSlice {
  group_key: string
  label: string
  requests: number
  share: number
}

export interface UsageStatisticsBreakdownResponse {
  parent_group_by: GatewayUsageStatsGroupBy
  parent_group_key: string
  breakdown_by: UsageStatisticsBreakdownBy
  parent_requests: number
  items: UsageStatisticsBreakdownSlice[]
}

export type GatewayUsageStatsBreakdownQuery = Omit<
  GatewayUsageStatsQuery,
  'group_by' | 'page' | 'page_size'
> & {
  parent_group_by: GatewayUsageStatsGroupBy
  parent_group_key: string
  breakdown_by: UsageStatisticsBreakdownBy
  top_n?: number
}

function buildUsageStatsBreakdownSearch(
  params: GatewayUsageStatsBreakdownQuery
): Record<string, string | string[]> {
  const search = buildUsageStatsSearch(params)
  search.parent_group_by = params.parent_group_by
  search.parent_group_key = params.parent_group_key
  search.breakdown_by = params.breakdown_by
  if (params.top_n !== undefined) search.top_n = String(params.top_n)
  return search
}

export const statsApi = {
  usageStats: (teamId: string, params?: GatewayUsageStatsQuery) =>
    apiClient.get<GatewayUsageStatsResponse>(
      teamGatewayPath(teamId, '/dashboard/statistics'),
      buildUsageStatsSearch(params)
    ),

  usageStatsBreakdown: (teamId: string, params: GatewayUsageStatsBreakdownQuery) =>
    apiClient.get<UsageStatisticsBreakdownResponse>(
      teamGatewayPath(teamId, '/dashboard/statistics/breakdown'),
      buildUsageStatsBreakdownSearch(params)
    ),
} as const
