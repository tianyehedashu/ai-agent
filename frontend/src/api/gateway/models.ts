/**
 * AI Gateway · 团队 Gateway 模型与平台统计
 *
 * `GatewayModel` 是把上游凭据绑定为「可被调用的模型别名」的注册行。
 * - `name` 是 Gateway 内的路由名（chat completion 调用方传入的 `model`）
 * - 同一 capability 可注册多个 deployment 做负载均衡 / fallback（详见 routes）
 *
 * 可用模型列表（`/models/available`）综合系统模型 + 当前用户的 personal 模型，
 * 是聊天 / 试调下拉选择的统一来源。
 */

import { apiClient } from '@/api/client'
import type { AvailableModelsResponse, ModelTestStatus, ModelType } from '@/types/user-model'

import { GATEWAY_API_BASE } from './_base'

/** Gateway 团队模型（注册行） */
export interface GatewayModel {
  id: string
  /** 数据归属租户（工作区团队 UUID） */
  tenant_id?: string | null
  /** 与 tenant_id 同值，兼容旧字段 */
  team_id: string | null
  name: string
  capability: string
  real_model: string
  credential_id: string
  provider: string
  weight: number
  rpm_limit: number | null
  tpm_limit: number | null
  enabled: boolean
  tags?: Record<string, unknown> | null
  /** 选择器用特性类型（后端由 tags + capability 推导） */
  model_types?: string[]
  /** 与 ModelCapabilitySnapshot 对齐的扁平特性 */
  selector_capabilities?: Record<string, unknown>
  /** 上次连通性测试结果，未测过为 null */
  last_test_status: ModelTestStatus
  /** 上次连通性测试时间（ISO 8601），未测过为 null */
  last_tested_at: string | null
  /** 上次失败/不支持时的说明；成功或未测过为 null */
  last_test_reason: string | null
  /** 当前调用方客户套餐命中状态；管理列表可缺省 */
  entitlement_status?: 'active' | 'exhausted' | 'resetting' | 'expired' | 'none'
  entitlement_reset_at?: string | null
  created_at: string
}

/** GET /models/usage-summary 单条 route 的切片 */
export interface GatewayModelRouteUsageSlice {
  requests: number
  input_tokens: number
  output_tokens: number
  /** 后端 Decimal 序列化常为 JSON 字符串 */
  cost_usd: number | string
}

/** /models/usage-summary 单条 route 的工作区/个人聚合 */
export interface GatewayModelRouteUsageItem {
  route_name: string
  workspace: GatewayModelRouteUsageSlice
  user: GatewayModelRouteUsageSlice
}

/** GET /models/usage-summary；按日志 route_name = 注册名统计 */
export interface GatewayModelUsageSummary {
  start: string
  end: string
  items: GatewayModelRouteUsageItem[]
}

/** GET /admin/credential-stats（仅平台管理员） */
export interface PlatformCredentialStat {
  credential_id: string
  provider: string
  name: string
  scope: string
  scope_id: string | null
  is_active: boolean
  gateway_model_count: number
  requests: number
  input_tokens: number
  output_tokens: number
  cost_usd: number | string
  success_count: number
  failure_count: number
}

/** POST /models/{id}/test 与 /my-models/{id}/test 响应 */
export interface GatewayModelTestResult {
  success: boolean
  message: string
  model: string
  status: string
  tested_at: string
  reason: string | null
  response_preview?: string
}

/** GET /models/presets：平台预置模型模板 */
export interface GatewayModelPreset {
  id: string
  name: string
  provider: string
  real_model: string
  capability: string
  context_window: number
  input_price: number
  output_price: number
  supports_vision: boolean
  supports_tools: boolean
  supports_reasoning: boolean
  recommended_for: string[]
  description: string
  model_types?: string[]
  selector_capabilities?: Record<string, unknown>
}

/** POST /models 请求体 */
export interface GatewayModelCreateBody {
  name: string
  capability: string
  real_model: string
  credential_id: string
  provider: string
  weight?: number
  rpm_limit?: number | null
  tpm_limit?: number | null
  tags?: Record<string, unknown> | null
  enabled?: boolean
}

/** PATCH /models/{id}，与 GatewayModelUpdate 对齐 */
export interface GatewayModelUpdateBody {
  name?: string | null
  real_model?: string | null
  credential_id?: string | null
  weight?: number | null
  rpm_limit?: number | null
  tpm_limit?: number | null
  enabled?: boolean | null
  tags?: Record<string, unknown> | null
}

/** Models 资源 API */
export const modelsApi = {
  /**
   * 列出当前调用方可用的模型（系统模型 + 我的个人模型；按 type / provider / mode 过滤）。
   *
   * 注意：mode 与 capability 不同，是「试调模式」概念（chat / image_gen / video）。
   */
  listAvailableModels: (
    type?: ModelType,
    provider?: string,
    options?: { mode?: 'chat' | 'image_gen' | 'video' }
  ) => {
    const search: Record<string, string> = {}
    if (type) search.type = type
    if (provider) search.provider = provider
    if (options?.mode) search.mode = options.mode
    return apiClient.get<AvailableModelsResponse>(`${GATEWAY_API_BASE}/models/available`, search)
  },

  /** 列出当前团队的 GatewayModel 注册行 */
  listModels: (params?: { provider?: string; credential_id?: string }) =>
    apiClient.get<GatewayModel[]>(`${GATEWAY_API_BASE}/models`, params),
  /** 团队模型用量汇总（按 route 维度） */
  modelsUsageSummary: (params?: { days?: number; provider?: string }) =>
    apiClient.get<GatewayModelUsageSummary>(`${GATEWAY_API_BASE}/models/usage-summary`, params),
  /** 平台凭据用量与成功率统计（仅平台管理员） */
  adminCredentialStats: (params?: { days?: number }) =>
    apiClient.get<PlatformCredentialStat[]>(`${GATEWAY_API_BASE}/admin/credential-stats`, params),
  /** 平台预置模型模板（注册团队模型时的可选项） */
  listModelPresets: (params?: { provider?: string }) =>
    apiClient.get<GatewayModelPreset[]>(`${GATEWAY_API_BASE}/models/presets`, params),
  /** 创建团队 GatewayModel */
  createModel: (body: GatewayModelCreateBody) =>
    apiClient.post<GatewayModel>(`${GATEWAY_API_BASE}/models`, body),
  /** 更新团队 GatewayModel（部分字段） */
  updateModel: (id: string, body: GatewayModelUpdateBody) =>
    apiClient.patch<GatewayModel>(`${GATEWAY_API_BASE}/models/${id}`, body),
  /** 删除团队 GatewayModel */
  deleteModel: (id: string) => apiClient.delete<unknown>(`${GATEWAY_API_BASE}/models/${id}`),
  /** 对一条 Gateway 团队模型发起最小 LLM 调用，结果同步落到 last_test_status / last_tested_at */
  testModel: (id: string) =>
    apiClient.post<GatewayModelTestResult>(`${GATEWAY_API_BASE}/models/${id}/test`, {}),
} as const
