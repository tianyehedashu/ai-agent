/**
 * AI Gateway · 日志、详情与大盘
 *
 * `usage_aggregation` 在「日志/大盘/利润」三组接口共用，决定聚合维度：
 * - `workspace`（产品文案：团队）：按 URL 路径中的 teamId 过滤
 * - `user`（产品文案：我）：按当前登录账号跨团队聚合
 *
 * 字面量保留 `workspace` 是为了与预算 BudgetScope.team 字面量正交，避免 URL/JSON 中误读。
 */

import { apiClient } from '@/api/client'

import { teamGatewayPath } from './_base'

/** 日志/大盘聚合维度 */
export type GatewayUsageAggregation = 'workspace' | 'user'

/** 日志列表项（脱敏后） */
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

/** GET /logs/{id} 详情：含脱敏 prompt / 响应摘要等 */
export interface GatewayLogDetail extends GatewayLogItem {
  team_snapshot?: Record<string, unknown> | null
  route_snapshot?: Record<string, unknown> | null
  prompt_redacted?: Record<string, unknown> | null
  response_summary?: Record<string, unknown> | null
  metadata_extra?: Record<string, unknown> | null
  pricing_snapshot?: Record<string, unknown> | null
}

/** GET /dashboard/summary 响应 */
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
 * GET /logs 查询参数。
 *
 * 兼容 apiClient 的 params 签名：`Record<string, string | number | boolean | undefined>`。
 */
export type GatewayLogsQuery = {
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
}

/** GET /logs 响应 */
export interface GatewayLogsPage {
  items: GatewayLogItem[]
  total: number
  page: number
  page_size: number
}

/** Logs / Dashboard 资源 API */
export const logsApi = {
  /** 分页查询调用日志（按当前聚合维度过滤） */
  listLogs: (teamId: string, params?: GatewayLogsQuery) =>
    apiClient.get<GatewayLogsPage>(teamGatewayPath(teamId, '/logs'), params),
  /** 获取单条调用日志详情 */
  getLog: (teamId: string, id: string, params?: { usage_aggregation?: GatewayUsageAggregation }) =>
    apiClient.get<GatewayLogDetail>(teamGatewayPath(teamId, `/logs/${id}`), params),
  /** 大盘汇总（次/吞吐/成本/成功率/延迟） */
  dashboard: (
    teamId: string,
    params?: { days?: number; usage_aggregation?: GatewayUsageAggregation }
  ) => apiClient.get<DashboardSummary>(teamGatewayPath(teamId, '/dashboard/summary'), params),
} as const
