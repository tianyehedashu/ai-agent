/**
 * AI Gateway · 预算（Budget）
 *
 * 预算用于强约束特定 target_kind（system / tenant / key / user）在固定周期内的成本上限。
 * 超过 `soft_limit_usd` 触发告警；超过 `limit_usd` 触发拒绝。
 */

import { apiClient } from '@/api/client'

import { teamGatewayPath } from './_base'

export interface GatewayBudget {
  id: string
  target_kind: 'system' | 'tenant' | 'key' | 'user'
  target_id: string | null
  /** 仅成员总量/模型护栏行非空：护栏所属团队（按团队隔离） */
  tenant_id?: string | null
  /** 仅「成员 + 凭据(+模型)」行非空 */
  credential_id?: string | null
  period: 'daily' | 'monthly' | 'total'
  /** 仅限制某一模型时填写，否则为 null */
  model_name: string | null
  limit_usd: number | null
  /** 软上限（用于预警） */
  soft_limit_usd?: number | null
  limit_tokens: number | null
  limit_requests: number | null
  /** 图片生成张数上限（仅对 image 能力生效） */
  limit_images: number | null
  current_usd: number
  current_tokens: number
  current_requests: number
  /** 已用图片张数 */
  current_images: number
  reset_at: string | null
  /** 下一次重置时间（含 rolling / calendar 策略） */
  budget_reset_at?: string | null
  /** IANA 时区；日/月切本地时刻 */
  period_timezone?: string
  /** 本地日切时刻：自 00:00 起的分钟数 */
  period_reset_minutes?: number
  /** 月切日；daily/total 使用默认值 1 */
  period_reset_day?: number
}

/** PUT /budgets 请求体（与后端 BudgetUpsert 一致） */
export interface BudgetUpsertBody {
  target_kind: 'system' | 'tenant' | 'key' | 'user'
  target_id?: string | null
  period: 'daily' | 'monthly' | 'total'
  model_name?: string | null
  limit_usd?: number | null
  soft_limit_usd?: number | null
  limit_tokens?: number | null
  limit_requests?: number | null
  limit_images?: number | null
  period_timezone?: string | null
  period_reset_minutes?: number | null
  period_reset_day?: number | null
}

/** Budgets 资源 API */
export const budgetsApi = {
  /** 列出当前 scope 可见的预算 */
  listBudgets: (
    teamId: string,
    params?: { target_kind?: GatewayBudget['target_kind']; model_name?: string }
  ) => {
    const search = new URLSearchParams()
    if (params?.target_kind) search.set('target_kind', params.target_kind)
    if (params?.model_name) search.set('model_name', params.model_name)
    const qs = search.toString()
    const path = qs ? `/budgets?${qs}` : '/budgets'
    return apiClient.get<GatewayBudget[]>(teamGatewayPath(teamId, path))
  },
  /** 创建或更新预算（按 target_kind + target_id + period + model_name 主键去重） */
  upsertBudget: (teamId: string, body: BudgetUpsertBody) =>
    apiClient.put<GatewayBudget>(teamGatewayPath(teamId, '/budgets'), body),
  /** 删除预算 */
  deleteBudget: (teamId: string, id: string) =>
    apiClient.delete<unknown>(teamGatewayPath(teamId, `/budgets/${id}`)),
} as const
