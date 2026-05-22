/**
 * AI Gateway · 调用统计
 *
 * 团队路径下按调用日志聚合，支持组合筛选与单维度分组。
 */

import { apiClient } from '@/api/client'

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
  cache_hit_count: number
  success_rate: number
  cache_hit_rate: number
}

export interface GatewayUsageStatsItem extends GatewayUsageStatsMetric {
  group_key: string
  label: string
}

export interface GatewayUsageStatsResponse {
  start: string
  end: string
  group_by: GatewayUsageStatsGroupBy
  totals: GatewayUsageStatsMetric
  items: GatewayUsageStatsItem[]
}

export type GatewayUsageStatsQuery = {
  days?: number
  usage_aggregation?: GatewayUsageAggregation
  group_by?: GatewayUsageStatsGroupBy
  credential_id?: string
  user_id?: string
  team_id?: string
  model?: string
  provider?: string
  capability?: string
  status?: string
  vkey_id?: string
  limit?: number
}

export const statsApi = {
  usageStats: (teamId: string, params?: GatewayUsageStatsQuery) =>
    apiClient.get<GatewayUsageStatsResponse>(
      teamGatewayPath(teamId, '/dashboard/statistics'),
      params
    ),
} as const
