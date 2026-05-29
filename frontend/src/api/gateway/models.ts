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
import { buildPageQuerySearch } from '@/lib/pagination'
import type { PageQuery, PaginatedList } from '@/types'
import type { AvailableModelsResponse, ModelTestStatus, ModelType } from '@/types/user-model'

import { GATEWAY_API_BASE, teamGatewayPath } from './_base'

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
  /** 绑定 team 凭据展示名（列表 enrich） */
  credential_name?: string | null
  /** 绑定 team 凭据创建者 */
  credential_created_by_user_id?: string | null
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
  /** 注册表归属：team=团队注册行；system=平台预置行 */
  registry_kind?: 'team' | 'system'
  /** 系统模型可见性（inherit/public/restricted） */
  visibility?: 'inherit' | 'public' | 'restricted' | null
  /** 平台管理员：系统模型绑定的厂商凭据 */
  system_credential?: {
    id: string
    provider: string
    name: string
    visibility: 'public' | 'restricted'
  } | null
  /** 当前调用方客户套餐命中状态；管理列表可缺省 */
  entitlement_status?: 'active' | 'exhausted' | 'resetting' | 'expired' | 'none'
  entitlement_reset_at?: string | null
  created_at: string
}

/** POST /models/batch-delete 单条失败项 */
export interface GatewayModelBatchDeleteFailureItem {
  id: string
  code: string
  message: string
}

/** POST /models/batch-delete 响应 */
export interface GatewayModelBatchDeleteResponse {
  succeeded: string[]
  failed: GatewayModelBatchDeleteFailureItem[]
  grants_removed: number
  budgets_removed: number
}

/** POST /models/batch-resync-capabilities 响应 */
export interface GatewayModelBatchResyncCapabilitiesResponse {
  succeeded: string[]
  failed: GatewayModelBatchDeleteFailureItem[]
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

/** GET /managed-team-models/usage-summary 单条 route（含 team_id） */
export interface ManagedTeamModelRouteUsageItem extends GatewayModelRouteUsageItem {
  team_id: string
}

/** GET /models/usage-summary；按日志 route_name = 注册名统计 */
export interface GatewayModelUsageSummary extends PaginatedList<GatewayModelRouteUsageItem> {
  start: string
  end: string
}

/** GET /managed-team-models/usage-summary；跨团队协作团队 workspace axis */
export interface ManagedTeamModelUsageSummary extends PaginatedList<ManagedTeamModelRouteUsageItem> {
  start: string
  end: string
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

export type PlatformCredentialStatList = PaginatedList<PlatformCredentialStat>

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
  upstream_call_shape?: string | null
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
  /** 为 true 时从 LiteLLM model_cost 重算能力 tags（不持久化） */
  resync_capabilities?: boolean
  upstream_call_shape?: string | null
}

export type GatewayModelRegistryScope =
  | 'team'
  | 'system'
  | 'callable'
  | 'requestable'
  | 'system_requestable'

export interface ModelConnectivitySummary {
  total: number
  available: number
  unavailable: number
  success: number
  failed: number
  unknown: number
}

export interface GatewayModelListQuery extends PageQuery {
  registry_scope?: GatewayModelRegistryScope
  q?: string
  connectivity?: 'all' | 'success' | 'failed' | 'unknown'
  sort?: 'name' | 'created_at' | 'provider' | 'last_tested_at'
  order?: 'asc' | 'desc'
  provider?: string
  credential_id?: string
  /** 能力筛选（与 /models/available 的 type 一致；勿用 capability 查列表） */
  type?: string
  /** @deprecated 列表请用 type */
  capability?: string
  enabled?: boolean
}

export interface GatewayModelListResponse extends PaginatedList<GatewayModel> {
  connectivity_summary: ModelConnectivitySummary
}

export interface ManagedTeamModelListResponse extends GatewayModelListResponse {
  queried_team_count: number
  queried_personal_team_count: number
  queried_shared_team_count: number
  tenant_ids_with_models: string[]
}

/** GET /managed-team-model-credential-filters */
export interface ManagedTeamModelCredentialFilterItem {
  id: string
  name: string
  provider: string
  tenant_id: string
}

export interface ManagedTeamModelCredentialFilterListResponse {
  items: ManagedTeamModelCredentialFilterItem[]
  queried_team_count: number
}

export interface ListManagedTeamModelsParams extends Omit<GatewayModelListQuery, 'registry_scope'> {
  search?: string
}

export interface ManagedTeamModelUsageSummaryQuery extends PageQuery {
  days?: number
  provider?: string
  route_names?: string[]
  search?: string
}

export interface GatewayModelIdsResponse {
  ids: string[]
  /** 命中 max_ids 上限时为 true，调用方应提示或分批处理 */
  truncated?: boolean
}

export interface AvailableModelsListQuery extends PageQuery {
  q?: string
  connectivity?: 'all' | 'success' | 'failed' | 'unknown'
  sort?: 'name' | 'created_at' | 'provider' | 'last_tested_at'
  order?: 'asc' | 'desc'
  provider?: string
  /** Gateway 工作区团队（与 POST /chat gateway_team_id 一致） */
  gatewayTeamId?: string
}

function buildModelListSearch(params?: GatewayModelListQuery): Record<string, string> {
  const search: Record<string, string> = {}
  if (!params) return search
  if (params.registry_scope) search.registry_scope = params.registry_scope
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
  if (params.enabled !== undefined) search.enabled = String(params.enabled)
  return search
}

function buildAvailableModelsSearch(
  type?: ModelType,
  provider?: string,
  options?: { mode?: 'chat' | 'image_gen' | 'video' } & AvailableModelsListQuery
): Record<string, string> {
  const search: Record<string, string> = {}
  if (type) search.type = type
  if (provider) search.provider = provider
  if (options?.mode) search.mode = options.mode
  if (options?.page !== undefined) search.page = String(options.page)
  if (options?.page_size !== undefined) search.page_size = String(options.page_size)
  if (options?.q) search.q = options.q
  if (options?.connectivity && options.connectivity !== 'all') {
    search.connectivity = options.connectivity
  }
  if (options?.sort) search.sort = options.sort
  if (options?.order) search.order = options.order
  if (options?.gatewayTeamId) search.gateway_team_id = options.gatewayTeamId
  return search
}

/** 拉取 available 模型全部分页（选择器/Studio 等需跨页查找时使用） */
export async function fetchAllAvailableGatewayModels(
  type?: ModelType,
  provider?: string,
  options?: { mode?: 'chat' | 'image_gen' | 'video' } & Omit<
    AvailableModelsListQuery,
    'page' | 'page_size'
  >
): Promise<AvailableModelsResponse> {
  const pageSize = 200
  let page = 1
  const systemItems: AvailableModelsResponse['system_models']['items'] = []
  const userItems: AvailableModelsResponse['user_models']['items'] = []
  let connectivitySummary = {
    total: 0,
    available: 0,
    unavailable: 0,
    success: 0,
    failed: 0,
    unknown: 0,
  }
  for (;;) {
    const res = await modelsApi.listAvailableModels(type, provider, {
      ...options,
      page,
      page_size: pageSize,
    })
    systemItems.push(...res.system_models.items)
    userItems.push(...res.user_models.items)
    if (res.connectivity_summary) {
      connectivitySummary = res.connectivity_summary
    }
    if (!res.system_models.has_next && !res.user_models.has_next) break
    page += 1
  }
  return {
    system_models: {
      items: systemItems,
      total: systemItems.length,
      page: 1,
      page_size: systemItems.length || pageSize,
      has_next: false,
      has_prev: false,
    },
    user_models: {
      items: userItems,
      total: userItems.length,
      page: 1,
      page_size: userItems.length || pageSize,
      has_next: false,
      has_prev: false,
    },
    connectivity_summary: connectivitySummary,
  }
}

/** 拉取全部分页结果（管理面下拉等需全量列表时使用，page_size 上限 200） */
export async function fetchAllGatewayModelPages(
  teamId: string,
  params?: Omit<GatewayModelListQuery, 'page' | 'page_size'>
): Promise<GatewayModel[]> {
  const pageSize = 200
  let page = 1
  const all: GatewayModel[] = []
  for (;;) {
    const res = await modelsApi.listModels(teamId, { ...params, page, page_size: pageSize })
    all.push(...res.items)
    if (!res.has_next) break
    page += 1
  }
  return all
}

/** 跨团队 managed-team-models 全量分页拉取（批量运维编排用） */
export async function fetchAllManagedTeamModelPages(
  params?: Omit<ListManagedTeamModelsParams, 'page' | 'page_size'>
): Promise<GatewayModel[]> {
  const pageSize = 200
  let page = 1
  const all: GatewayModel[] = []
  for (;;) {
    const res = await modelsApi.listManagedTeamModels({ ...params, page, page_size: pageSize })
    all.push(...res.items)
    if (!res.has_next) break
    page += 1
  }
  return all
}

/** 当前筛选下的模型 id（批量操作；须检查 ``truncated``） */
export async function fetchGatewayModelIdsForBatch(
  teamId: string,
  params?: Omit<GatewayModelListQuery, 'page' | 'page_size'>
): Promise<GatewayModelIdsResponse> {
  return modelsApi.listModelIds(teamId, params)
}

/** Models 资源 API */
export interface GatewayModelUsageSummaryQuery extends PageQuery {
  days?: number
  provider?: string
  route_names?: string[]
}

function buildModelUsageSummarySearch(
  params?: GatewayModelUsageSummaryQuery
): Record<string, string | string[]> {
  const search: Record<string, string | string[]> = buildPageQuerySearch(params)
  if (!params) return search
  if (params.days !== undefined) search.days = String(params.days)
  if (params.provider) search.provider = params.provider
  if (params.route_names?.length) search.route_names = params.route_names
  return search
}

function buildAdminCredentialStatsSearch(
  params?: PageQuery & { days?: number }
): Record<string, string> {
  const search = buildPageQuerySearch(params)
  if (params?.days !== undefined) search.days = String(params.days)
  return search
}

function buildManagedTeamModelUsageSummarySearch(
  params?: ManagedTeamModelUsageSummaryQuery
): Record<string, string | string[]> {
  const search: Record<string, string | string[]> = buildPageQuerySearch(params)
  if (!params) return search
  if (params.days !== undefined) search.days = String(params.days)
  if (params.provider) search.provider = params.provider
  if (params.route_names?.length) search.route_names = params.route_names
  if (params.search) search.search = params.search
  return search
}

export const modelsApi = {
  /**
   * 列出当前调用方可用的模型（系统模型 + 我的个人模型；按 type / provider / mode 过滤）。
   *
   * 注意：mode 与 capability 不同，是「试调模式」概念（chat / image_gen / video）。
   */
  listAvailableModels: (
    type?: ModelType,
    provider?: string,
    options?: { mode?: 'chat' | 'image_gen' | 'video' } & AvailableModelsListQuery
  ) =>
    apiClient.get<AvailableModelsResponse>(
      `${GATEWAY_API_BASE}/models/available`,
      buildAvailableModelsSearch(type, provider, options)
    ),

  /** 列出 Gateway 模型注册行或合并可调用列表（分页 envelope） */
  listModels: (teamId: string, params?: GatewayModelListQuery) =>
    apiClient.get<GatewayModelListResponse>(
      teamGatewayPath(teamId, '/models'),
      buildModelListSearch(params)
    ),

  /** 跨可写团队聚合 team registry 模型（分页） */
  listManagedTeamModels: (params?: ListManagedTeamModelsParams) => {
    const search: Record<string, string> = buildModelListSearch(params)
    if (params?.search) search.search = params.search
    return apiClient.get<ManagedTeamModelListResponse>(
      `${GATEWAY_API_BASE}/managed-team-models`,
      search
    )
  },

  /** 跨协作团队模型用量汇总（按 route + team_id 维度） */
  managedTeamModelsUsageSummary: (params?: ManagedTeamModelUsageSummaryQuery) =>
    apiClient.get<ManagedTeamModelUsageSummary>(
      `${GATEWAY_API_BASE}/managed-team-models/usage-summary`,
      buildManagedTeamModelUsageSummarySearch(params)
    ),

  /** 团队 Tab 模型列表：按凭据筛选下拉（注册模型绑定，含成员可见名） */
  listManagedTeamModelCredentialFilters: () =>
    apiClient.get<ManagedTeamModelCredentialFilterListResponse>(
      `${GATEWAY_API_BASE}/managed-team-model-credential-filters`
    ),

  /** 单条团队/系统注册模型 */
  getModel: (teamId: string, id: string, params?: Pick<GatewayModelListQuery, 'registry_scope'>) =>
    apiClient.get<GatewayModel>(
      teamGatewayPath(teamId, `/models/${id}`),
      params?.registry_scope ? { registry_scope: params.registry_scope } : undefined
    ),

  /** 当前筛选条件下的全部模型 id（批量操作） */
  listModelIds: (teamId: string, params?: GatewayModelListQuery) =>
    apiClient.get<GatewayModelIdsResponse>(
      teamGatewayPath(teamId, '/models/ids'),
      buildModelListSearch(params)
    ),

  /** 团队模型用量汇总（按 route 维度） */
  modelsUsageSummary: (teamId: string, params?: GatewayModelUsageSummaryQuery) =>
    apiClient.get<GatewayModelUsageSummary>(
      teamGatewayPath(teamId, '/models/usage-summary'),
      buildModelUsageSummarySearch(params)
    ),
  /** 平台凭据用量与成功率统计（仅平台管理员） */
  adminCredentialStats: (teamId: string, params?: PageQuery & { days?: number }) =>
    apiClient.get<PlatformCredentialStatList>(
      teamGatewayPath(teamId, '/admin/credential-stats'),
      buildAdminCredentialStatsSearch(params)
    ),
  /** 平台预置模型模板（注册团队模型时的可选项） */
  listModelPresets: (teamId: string, params?: { provider?: string }) =>
    apiClient.get<GatewayModelPreset[]>(teamGatewayPath(teamId, '/models/presets'), params),
  /** 创建团队 GatewayModel */
  createModel: (teamId: string, body: GatewayModelCreateBody) =>
    apiClient.post<GatewayModel>(teamGatewayPath(teamId, '/models'), body),
  /** 更新团队 GatewayModel（部分字段） */
  updateModel: (teamId: string, id: string, body: GatewayModelUpdateBody) =>
    apiClient.patch<GatewayModel>(teamGatewayPath(teamId, `/models/${id}`), body),
  /** 删除团队 GatewayModel */
  deleteModel: (teamId: string, id: string) =>
    apiClient.delete<unknown>(teamGatewayPath(teamId, `/models/${id}`)),
  /** 批量删除 GatewayModel（部分成功） */
  batchDeleteModels: (teamId: string, modelIds: string[]) =>
    apiClient.post<GatewayModelBatchDeleteResponse>(
      teamGatewayPath(teamId, '/models/batch-delete'),
      { model_ids: modelIds }
    ),
  /** 批量从 LiteLLM 同步能力 tags（部分成功） */
  batchResyncCapabilities: (teamId: string, modelIds: string[]) =>
    apiClient.post<GatewayModelBatchResyncCapabilitiesResponse>(
      teamGatewayPath(teamId, '/models/batch-resync-capabilities'),
      { model_ids: modelIds }
    ),
  /** 对一条 Gateway 团队模型发起最小 LLM 调用，结果同步落到 last_test_status / last_tested_at */
  testModel: (teamId: string, id: string) =>
    apiClient.post<GatewayModelTestResult>(teamGatewayPath(teamId, `/models/${id}/test`), {}),
} as const
