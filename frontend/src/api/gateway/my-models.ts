/**
 * AI Gateway · 个人 Gateway 模型（BYOK / 私有路由）
 *
 * 与团队 GatewayModel 形状相近，但 owner 是当前用户、scope 为 personal，
 * 仅本人可见、可调用。用于自带 Key 接入第三方模型供应商。
 */

import { apiClient } from '@/api/client'
import type { ModelTestStatus, ModelType } from '@/types/user-model'

import { GATEWAY_API_BASE } from './_base'

/** GET /my-models 列表项（与模型选择器 personal 段形状对齐） */
export interface PersonalGatewayModel {
  id: string
  user_id: string | null
  anonymous_user_id: string | null
  display_name: string
  provider: string
  model_id: string
  api_key_masked: string | null
  has_api_key: boolean
  api_base: string | null
  credential_id: string
  model_types: ModelType[]
  config: Record<string, unknown> | null
  is_active: boolean
  is_system: boolean
  capability: string
  name: string
  last_test_status: ModelTestStatus
  last_tested_at: string | null
  last_test_reason: string | null
  /** 当前调用方客户套餐命中状态；管理列表可缺省 */
  entitlement_status?: 'active' | 'exhausted' | 'resetting' | 'expired' | 'none'
  entitlement_reset_at?: string | null
  created_at: string | null
  updated_at: string | null
}

/** POST /my-models 请求体 */
export interface PersonalGatewayModelCreateBody {
  display_name: string
  provider: string
  model_id: string
  credential_id: string
  model_types: ModelType[]
  tags?: Record<string, unknown> | null
}

/** PATCH /my-models/{id} 请求体 */
export interface PersonalGatewayModelUpdateBody {
  display_name?: string
  model_id?: string
  credential_id?: string
  is_active?: boolean
}

// 测试结果与团队侧共用类型，从 models 模块导出，避免重复声明
import type { GatewayModelTestResult } from './models'

/** My-models 资源 API */
export const myModelsApi = {
  /** 列出当前用户的个人 Gateway 模型 */
  listMyModels: (params?: { provider?: string }) =>
    apiClient.get<PersonalGatewayModel[]>(`${GATEWAY_API_BASE}/my-models`, params),
  /** 创建个人 Gateway 模型；响应为该模型可能产生的全部 routing 行 */
  createMyModel: (body: PersonalGatewayModelCreateBody) =>
    apiClient.post<PersonalGatewayModel[]>(`${GATEWAY_API_BASE}/my-models`, body),
  /** 更新个人 Gateway 模型 */
  updateMyModel: (id: string, body: PersonalGatewayModelUpdateBody) =>
    apiClient.patch<PersonalGatewayModel>(`${GATEWAY_API_BASE}/my-models/${id}`, body),
  /** 删除个人 Gateway 模型 */
  deleteMyModel: (id: string) => apiClient.delete<unknown>(`${GATEWAY_API_BASE}/my-models/${id}`),
  /** 对个人 Gateway 模型发起最小连通性测试 */
  testMyModel: (id: string) =>
    apiClient.post<GatewayModelTestResult>(`${GATEWAY_API_BASE}/my-models/${id}/test`, {}),
} as const
