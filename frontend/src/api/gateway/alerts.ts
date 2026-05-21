/**
 * AI Gateway · 告警规则（Alert Rules）
 *
 * 告警规则用于在错误率、预算使用率、P95 延迟、调用速率等指标超阈值时通知 channel。
 */

import { apiClient } from '@/api/client'

import { teamGatewayPath } from './_base'

export interface AlertRule {
  id: string
  tenant_id?: string | null
  team_id: string | null
  name: string
  description: string | null
  metric: string
  threshold: number
  /** 评估窗口（分钟） */
  window_minutes: number
  /** 通知渠道配置（webhook / email / slack 等） */
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

/** Alerts 资源 API */
export const alertsApi = {
  /** 列出当前 scope 的告警规则 */
  listAlerts: (teamId: string) =>
    apiClient.get<AlertRule[]>(teamGatewayPath(teamId, '/alerts/rules')),
  /** 创建告警规则 */
  createAlert: (teamId: string, body: AlertRuleCreateBody) =>
    apiClient.post<AlertRule>(teamGatewayPath(teamId, '/alerts/rules'), body),
  /** 删除告警规则 */
  deleteAlert: (teamId: string, id: string) =>
    apiClient.delete<unknown>(teamGatewayPath(teamId, `/alerts/rules/${id}`)),
} as const
