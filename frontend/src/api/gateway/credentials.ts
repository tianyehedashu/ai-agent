/**
 * AI Gateway · 上游凭据（Provider Credential）资源
 *
 * 凭据是 Gateway 调用上游模型供应商的认证主体（API Key + Base URL + 额外参数）。
 * 分两类：
 * - 团队/系统凭据（`/credentials`）：由团队 admin 或平台管理员维护；可被注册为团队 GatewayModel
 * - 我的凭据（`/my-credentials`）：BYOK 个人凭据；仅本人可见，注册到 PersonalGatewayModel
 *
 * 上游探测与批量导入（probe / batch-import-models）是同形态接口，分别走 team / personal 路径。
 */

import { apiClient } from '@/api/client'
import { fetchAllPaginatedPages, MAX_PAGE_SIZE } from '@/lib/pagination'
import type { PaginatedList } from '@/types'

import { GATEWAY_API_BASE, teamGatewayPath } from './_base'
import { normalizeCredential, type ProviderCredentialWire } from './credential-normalize'

export { normalizeCredential, normalizeCredentialScope } from './credential-normalize'
export type { ProviderCredentialWire } from './credential-normalize'

/** 凭据摘要（无密钥 / api_base / extra），供 member 解析模型上的 credential_id */
export interface CredentialSummary {
  id: string
  provider: string
  name: string
  scope: 'user' | 'team' | 'system' | null
  is_active: boolean
  is_config_managed: boolean
  created_by_user_id?: string | null
  created_by_label?: string | null
  management_access?: 'full' | 'metadata'
}

/** Playground 聚合凭据摘要：含解析模型/Key 所需的团队上下文 */
export interface PlaygroundCredentialSummary extends CredentialSummary {
  context_team_id: string | null
}

export interface CredentialApiBases {
  openai_compat?: string | null
  anthropic_native?: string | null
}

/** 上游凭据列表项（不含明文） */
export interface ProviderCredential {
  id: string
  /** 租户（团队）凭据归属；与 scope=user 互斥 */
  tenant_id: string | null
  scope: 'system' | 'team' | 'user'
  scope_id: string | null
  provider: string
  name: string
  api_base: string | null
  api_bases?: CredentialApiBases | null
  profile_id?: string | null
  profile_label?: string | null
  effective_api_base_openai?: string | null
  effective_api_base_anthropic?: string | null
  is_active: boolean
  /** app.toml/环境变量同步托管的 system 凭据；UI 不允许直接修改 */
  is_config_managed?: boolean
  /** 系统凭据可见性（public / restricted） */
  visibility?: 'public' | 'restricted' | null
  extra: Record<string, unknown> | null
  created_at: string
  /** 后端解密后掩码展示，不含完整密钥 */
  api_key_masked: string
  /** 团队 scope 凭据创建者 */
  created_by_user_id?: string | null
  /** 提供者展示名（平台 / 用户 / 团队凭据创建者） */
  created_by_label?: string | null
  /** full=可管理；metadata=团队内仅展示非敏感字段 */
  management_access?: 'full' | 'metadata'
}

/** 团队/系统凭据创建体 */
export interface ProviderCredentialCreateBody {
  provider: string
  name: string
  api_key: string
  api_base?: string
  api_bases?: CredentialApiBases | null
  profile_id?: string | null
  extra?: Record<string, unknown>
  /** 默认 team；system 仅平台管理员可创建 */
  scope?: 'team' | 'system'
}

/** 我的凭据创建体（不含 scope；强制为 user） */
export interface MyCredentialCreateBody {
  provider: string
  name: string
  api_key: string
  api_base?: string | null
  api_bases?: CredentialApiBases | null
  profile_id?: string | null
  extra?: Record<string, unknown>
}

/** PATCH /credentials/{id} 与 /my-credentials/{id} 共用字段 */
export interface GatewayCredentialUpdateBody {
  name?: string | null
  api_key?: string | null
  api_base?: string | null
  api_bases?: CredentialApiBases | null
  profile_id?: string | null
  extra?: Record<string, unknown> | null
  is_active?: boolean | null
}

// ---------- 上游探测 / 批量导入 ----------

export type CredentialProbeSupport = 'full' | 'partial' | 'unsupported' | 'error'

export type CredentialProbeUpstream = 'openai_compatible' | 'none'

/** 上游模型列表中的单条目 */
export interface CredentialUpstreamItem {
  id: string
  owned_by?: string | null
  /** 该上游 id 在本凭据下是否已有注册行 */
  already_registered?: boolean
  /** 已注册的 Gateway 别名（route name） */
  registered_names?: string[]
  /** 服务端推断的 personal model_types；空数组表示不可导入 */
  inferred_model_types?: string[]
}

/** POST /credentials/{id}/probe 与 /my-credentials/{id}/probe 响应 */
export interface CredentialProbeResult {
  credential_id: string
  probe_at: string
  support: CredentialProbeSupport
  upstream: CredentialProbeUpstream
  items: CredentialUpstreamItem[]
  message?: string | null
  http_status?: number | null
}

export interface PersonalModelBatchImportItemBody {
  upstream_model_id: string
  model_types: string[]
}

/** /my-credentials/{id}/batch-import-models 请求体 */
export interface PersonalModelBatchImportBody {
  provider: string
  /** 按条指定类型（优先） */
  items?: PersonalModelBatchImportItemBody[]
  /** @deprecated 与 model_types 一起使用 */
  upstream_model_ids?: string[]
  model_types?: string[]
  display_name_prefix?: string | null
  enabled?: boolean
  tags?: Record<string, unknown> | null
}

export interface PersonalModelBatchImportCreatedItem {
  upstream_model_id: string
  gateway_model_ids: string[]
}

/** 团队/个人批量导入共用的失败项 */
export interface BatchImportFailureItem {
  upstream_model_id: string
  reason: string
}

export interface PersonalModelBatchImportResponse {
  credential_id: string
  created: PersonalModelBatchImportCreatedItem[]
  failed: BatchImportFailureItem[]
}

/** /credentials/{id}/batch-import-models 单条请求项 */
export interface TeamGatewayModelBatchImportItem {
  upstream_model_id: string
  name?: string | null
}

export interface TeamGatewayModelBatchImportBody {
  provider: string
  capability?: string
  weight?: number
  rpm_limit?: number | null
  tpm_limit?: number | null
  tags?: Record<string, unknown> | null
  enabled?: boolean
  items: TeamGatewayModelBatchImportItem[]
}

export interface TeamGatewayModelBatchImportCreatedItem {
  upstream_model_id: string
  gateway_model_id: string
}

export interface TeamGatewayModelBatchImportResponse {
  credential_id: string
  created: TeamGatewayModelBatchImportCreatedItem[]
  failed: BatchImportFailureItem[]
}

// ---------- 凭据 + 模型批量导入到团队 ----------

export interface ImportedModelSummary {
  source_model_id?: string | null
  name: string
  real_model: string
}

export interface ModelImportFailureItem {
  model_name: string
  reason: string
}

export interface ImportedCredentialItem {
  source_credential_id: string
  new_credential: ProviderCredential
  models_created: ImportedModelSummary[]
  models_failed: ModelImportFailureItem[]
}

export interface CredentialCopyFailureItem {
  credential_id: string
  reason: string
}

export interface ImportCredentialsWithModelsResponse {
  succeeded: ImportedCredentialItem[]
  failed: CredentialCopyFailureItem[]
}

export type CredentialCopyEndpoint = { kind: 'personal' } | { kind: 'team'; team_id: string }

export interface CopyCredentialsWithModelsBody {
  credential_ids: string[]
  source: CredentialCopyEndpoint
  destination: CredentialCopyEndpoint
}

/** GET /managed-team-credentials 分页响应 */
export interface ManagedTeamCredentialListResponse extends PaginatedList<ProviderCredential> {
  queried_team_count: number
  queried_personal_team_count: number
  queried_shared_team_count: number
  /** search 过滤范围内至少有一条 team-scope 凭据的 tenant_id（去重） */
  tenant_ids_with_credentials: string[]
}

export interface ListManagedTeamCredentialsParams {
  page?: number
  page_size?: number
  search?: string
}

interface ManagedTeamCredentialListWire extends PaginatedList<ProviderCredentialWire> {
  queried_team_count: number
  queried_personal_team_count: number
  queried_shared_team_count: number
  tenant_ids_with_credentials: string[]
}

/** Credentials 资源 API（团队/系统 + 我的 + 探测/批量导入 + 从 app.toml 导入） */
export const credentialsApi = {
  // --- 团队 / 系统凭据 ---
  /** 列出团队/系统可见凭据 */
  listCredentials: async (teamId: string) => {
    const rows = await apiClient.get<ProviderCredentialWire[]>(
      teamGatewayPath(teamId, '/credentials')
    )
    return rows.map(normalizeCredential)
  },
  /** 凭据摘要目录（含 system；团队 member 可读，无密钥字段） */
  listCredentialSummaries: (teamId: string) =>
    apiClient.get<CredentialSummary[]>(teamGatewayPath(teamId, '/credentials/summaries')),
  /** Playground / 调用指南：跨 membership 聚合个人 + 团队 + 系统凭据摘要 */
  listPlaygroundCredentialSummaries: () =>
    apiClient.get<PlaygroundCredentialSummary[]>(
      `${GATEWAY_API_BASE}/playground/credential-summaries`
    ),
  /** 获取单条团队/系统凭据详情 */
  getCredential: async (teamId: string, id: string) => {
    const row = await apiClient.get<ProviderCredentialWire>(
      teamGatewayPath(teamId, `/credentials/${id}`)
    )
    return normalizeCredential(row)
  },
  /** 揭示团队/系统凭据明文（要求 owner / admin） */
  revealCredential: (teamId: string, id: string) =>
    apiClient.get<{ api_key: string }>(teamGatewayPath(teamId, `/credentials/${id}/reveal`)),
  /** 创建团队/系统凭据；scope 默认 team，system 仅平台管理员 */
  createCredential: async (teamId: string, body: ProviderCredentialCreateBody) => {
    const row = await apiClient.post<ProviderCredentialWire>(
      teamGatewayPath(teamId, '/credentials'),
      body
    )
    return normalizeCredential(row)
  },
  /** 更新团队/系统凭据；is_config_managed 凭据可能被服务端拒绝写入 */
  updateCredential: async (teamId: string, id: string, body: GatewayCredentialUpdateBody) => {
    const row = await apiClient.patch<ProviderCredentialWire>(
      teamGatewayPath(teamId, `/credentials/${id}`),
      body
    )
    return normalizeCredential(row)
  },
  /** 删除团队/系统凭据（不可恢复） */
  deleteCredential: (teamId: string, id: string) =>
    apiClient.delete<unknown>(teamGatewayPath(teamId, `/credentials/${id}`)),

  /** 跨可写团队聚合的团队 scope 凭据（分页） */
  listManagedTeamCredentials: async (params?: ListManagedTeamCredentialsParams) => {
    const data = await apiClient.get<ManagedTeamCredentialListWire>(
      `${GATEWAY_API_BASE}/managed-team-credentials`,
      {
        page: params?.page,
        page_size: params?.page_size,
        search: params?.search,
      }
    )
    return {
      ...data,
      items: data.items.map(normalizeCredential),
      tenant_ids_with_credentials: data.tenant_ids_with_credentials,
    }
  },

  // --- 我的（BYOK 个人）凭据 ---
  /** 列出我的个人凭据 */
  listMyCredentials: async () => {
    const rows = await apiClient.get<ProviderCredentialWire[]>(`${GATEWAY_API_BASE}/my-credentials`)
    return rows.map(normalizeCredential)
  },
  /** 揭示我的凭据明文 */
  revealMyCredential: (id: string) =>
    apiClient.get<{ api_key: string }>(`${GATEWAY_API_BASE}/my-credentials/${id}/reveal`),
  /** 创建个人凭据 */
  createMyCredential: async (body: MyCredentialCreateBody) => {
    const row = await apiClient.post<ProviderCredentialWire>(
      `${GATEWAY_API_BASE}/my-credentials`,
      body
    )
    return normalizeCredential(row)
  },
  /** 更新个人凭据 */
  updateMyCredential: async (id: string, body: GatewayCredentialUpdateBody) => {
    const row = await apiClient.patch<ProviderCredentialWire>(
      `${GATEWAY_API_BASE}/my-credentials/${id}`,
      body
    )
    return normalizeCredential(row)
  },
  /** 删除个人凭据 */
  deleteMyCredential: (id: string) =>
    apiClient.delete<unknown>(`${GATEWAY_API_BASE}/my-credentials/${id}`),

  // --- 探测 + 批量导入（同形态，team / personal 两条路径） ---
  /** 探测我的凭据可用的上游模型列表 */
  probeMyCredential: (credentialId: string) =>
    apiClient.post<CredentialProbeResult>(
      `${GATEWAY_API_BASE}/my-credentials/${credentialId}/probe`,
      {}
    ),
  /** 基于探测结果批量导入到我的 GatewayModel */
  batchImportMyModelsFromUpstream: (credentialId: string, body: PersonalModelBatchImportBody) =>
    apiClient.post<PersonalModelBatchImportResponse>(
      `${GATEWAY_API_BASE}/my-credentials/${credentialId}/batch-import-models`,
      body
    ),
  /** 探测团队凭据可用的上游模型列表 */
  probeTeamCredential: (teamId: string, credentialId: string) =>
    apiClient.post<CredentialProbeResult>(
      teamGatewayPath(teamId, `/credentials/${credentialId}/probe`),
      {}
    ),
  /** 基于探测结果批量导入到团队 GatewayModel */
  batchImportTeamModelsFromUpstream: (
    teamId: string,
    credentialId: string,
    body: TeamGatewayModelBatchImportBody
  ) =>
    apiClient.post<TeamGatewayModelBatchImportResponse>(
      teamGatewayPath(teamId, `/credentials/${credentialId}/batch-import-models`),
      body
    ),

  /** 将当前用户的全部 user-scope 凭据复制到团队；返回新建条数 */
  importFromUserConfig: (teamId: string) =>
    apiClient.post<{ created: number }>(teamGatewayPath(teamId, '/credentials/import')),

  /** 跨个人/团队 scope 复制凭据及关联模型 */
  copyCredentialsWithModels: async (body: CopyCredentialsWithModelsBody) => {
    const data = await apiClient.post<{
      succeeded: Array<{
        source_credential_id: string
        new_credential: ProviderCredentialWire
        models_created: ImportedModelSummary[]
        models_failed: ModelImportFailureItem[]
      }>
      failed: CredentialCopyFailureItem[]
    }>(`${GATEWAY_API_BASE}/credentials/copy-with-models`, body)
    return {
      ...data,
      succeeded: data.succeeded.map((s) => ({
        ...s,
        new_credential: normalizeCredential(s.new_credential),
      })),
    } as ImportCredentialsWithModelsResponse
  },
} as const

/** 拉取当前 actor 可见的全部团队 scope 凭据（筛选下拉等需全量时使用） */
export async function fetchAllManagedTeamCredentials(
  params?: Omit<ListManagedTeamCredentialsParams, 'page' | 'page_size'>
): Promise<ProviderCredential[]> {
  return fetchAllPaginatedPages(
    (page, page_size) => credentialsApi.listManagedTeamCredentials({ ...params, page, page_size }),
    MAX_PAGE_SIZE
  )
}
