/**
 * AI Gateway · 个人 Gateway 模型（BYOK / 私有路由）
 *
 * 与团队 GatewayModel 形状相近，但 owner 是当前用户、scope 为 personal，
 * 仅本人可见、可调用。用于自带 Key 接入第三方模型供应商。
 */

import { apiClient } from '@/api/client'
import { fetchAllPaginatedPages } from '@/lib/pagination'
import type { PageQuery, PaginatedList } from '@/types'
import type { ModelTestStatus, ModelType } from '@/types/user-model'

import { GATEWAY_API_BASE } from './_base'

import type {
  GatewayModelBatchDeleteResponse,
  GatewayModelTestResult,
  ModelConnectivitySummary,
} from './models'

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
  selector_capabilities?: Record<string, unknown>
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

export interface PersonalModelListQuery extends PageQuery {
  q?: string
  connectivity?: 'all' | 'success' | 'failed' | 'unknown'
  sort?: 'name' | 'created_at' | 'provider' | 'last_tested_at'
  order?: 'asc' | 'desc'
  provider?: string
  credential_id?: string
  type?: string
}

export interface PersonalModelListResponse extends PaginatedList<PersonalGatewayModel> {
  connectivity_summary: ModelConnectivitySummary
}

function buildPersonalModelListSearch(params?: PersonalModelListQuery): Record<string, string> {
  const search: Record<string, string> = {}
  if (!params) return search
  if (params.page !== undefined) search.page = String(params.page)
  if (params.page_size !== undefined) search.page_size = String(params.page_size)
  if (params.q) search.q = params.q
  if (params.connectivity && params.connectivity !== 'all')
    search.connectivity = params.connectivity
  if (params.sort) search.sort = params.sort
  if (params.order) search.order = params.order
  if (params.provider) search.provider = params.provider
  if (params.credential_id) search.credential_id = params.credential_id
  if (params.type) search.type = params.type
  return search
}

/** 拉取全部个人模型分页（下拉/预算等需全量时使用） */
export async function fetchAllPersonalGatewayModels(
  params?: Omit<PersonalModelListQuery, 'page' | 'page_size'>
): Promise<PersonalGatewayModel[]> {
  return fetchAllPaginatedPages((page, page_size) =>
    myModelsApi.listMyModels({ ...params, page, page_size })
  )
}

/** My-models 资源 API */
export const myModelsApi = {
  /** 列出当前用户的个人 Gateway 模型（分页） */
  listMyModels: (params?: PersonalModelListQuery) =>
    apiClient.get<PersonalModelListResponse>(
      `${GATEWAY_API_BASE}/my-models`,
      buildPersonalModelListSearch(params)
    ),

  /** 单条个人 Gateway 模型 */
  getMyModel: (id: string) =>
    apiClient.get<PersonalGatewayModel>(`${GATEWAY_API_BASE}/my-models/${id}`),
  /** 创建个人 Gateway 模型；响应为该模型可能产生的全部 routing 行 */
  createMyModel: (body: PersonalGatewayModelCreateBody) =>
    apiClient.post<PersonalGatewayModel[]>(`${GATEWAY_API_BASE}/my-models`, body),
  /** 更新个人 Gateway 模型 */
  updateMyModel: (id: string, body: PersonalGatewayModelUpdateBody) =>
    apiClient.patch<PersonalGatewayModel>(`${GATEWAY_API_BASE}/my-models/${id}`, body),
  /** 删除个人 Gateway 模型 */
  deleteMyModel: (id: string) => apiClient.delete<unknown>(`${GATEWAY_API_BASE}/my-models/${id}`),
  /** 批量删除个人 Gateway 模型（部分成功） */
  batchDeleteMyModels: (modelIds: string[]) =>
    apiClient.post<GatewayModelBatchDeleteResponse>(`${GATEWAY_API_BASE}/my-models/batch-delete`, {
      model_ids: modelIds,
    }),
  /** 对个人 Gateway 模型发起最小连通性测试 */
  testMyModel: (id: string) =>
    apiClient.post<GatewayModelTestResult>(`${GATEWAY_API_BASE}/my-models/${id}/test`, {}),
} as const
