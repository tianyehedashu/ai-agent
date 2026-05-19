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

import { GATEWAY_API_BASE } from './_base'

/** 上游凭据列表项（不含明文） */
export interface ProviderCredential {
  id: string
  scope: 'system' | 'team' | 'user'
  scope_id: string | null
  provider: string
  name: string
  api_base: string | null
  is_active: boolean
  /** app.toml/环境变量同步托管的 system 凭据；UI 不允许直接修改 */
  is_config_managed?: boolean
  extra: Record<string, unknown> | null
  created_at: string
  /** 后端解密后掩码展示，不含完整密钥 */
  api_key_masked: string
}

/** 团队/系统凭据创建体 */
export interface ProviderCredentialCreateBody {
  provider: string
  name: string
  api_key: string
  api_base?: string
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
  extra?: Record<string, unknown>
}

/** PATCH /credentials/{id} 与 /my-credentials/{id} 共用字段 */
export interface GatewayCredentialUpdateBody {
  name?: string | null
  api_key?: string | null
  api_base?: string | null
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

/** /my-credentials/{id}/batch-import-models 请求体 */
export interface PersonalModelBatchImportBody {
  provider: string
  upstream_model_ids: string[]
  model_types: string[]
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

/** Credentials 资源 API（团队/系统 + 我的 + 探测/批量导入 + 从 app.toml 导入） */
export const credentialsApi = {
  // --- 团队 / 系统凭据 ---
  /** 列出团队/系统可见凭据 */
  listCredentials: () => apiClient.get<ProviderCredential[]>(`${GATEWAY_API_BASE}/credentials`),
  /** 获取单条团队/系统凭据详情 */
  getCredential: (id: string) =>
    apiClient.get<ProviderCredential>(`${GATEWAY_API_BASE}/credentials/${id}`),
  /** 揭示团队/系统凭据明文（要求 owner / admin） */
  revealCredential: (id: string) =>
    apiClient.get<{ api_key: string }>(`${GATEWAY_API_BASE}/credentials/${id}/reveal`),
  /** 创建团队/系统凭据；scope 默认 team，system 仅平台管理员 */
  createCredential: (body: ProviderCredentialCreateBody) =>
    apiClient.post<ProviderCredential>(`${GATEWAY_API_BASE}/credentials`, body),
  /** 更新团队/系统凭据；is_config_managed 凭据可能被服务端拒绝写入 */
  updateCredential: (id: string, body: GatewayCredentialUpdateBody) =>
    apiClient.patch<ProviderCredential>(`${GATEWAY_API_BASE}/credentials/${id}`, body),
  /** 删除团队/系统凭据（不可恢复） */
  deleteCredential: (id: string) =>
    apiClient.delete<unknown>(`${GATEWAY_API_BASE}/credentials/${id}`),

  // --- 我的（BYOK 个人）凭据 ---
  /** 列出我的个人凭据 */
  listMyCredentials: () =>
    apiClient.get<ProviderCredential[]>(`${GATEWAY_API_BASE}/my-credentials`),
  /** 揭示我的凭据明文 */
  revealMyCredential: (id: string) =>
    apiClient.get<{ api_key: string }>(`${GATEWAY_API_BASE}/my-credentials/${id}/reveal`),
  /** 创建个人凭据 */
  createMyCredential: (body: MyCredentialCreateBody) =>
    apiClient.post<ProviderCredential>(`${GATEWAY_API_BASE}/my-credentials`, body),
  /** 更新个人凭据 */
  updateMyCredential: (id: string, body: GatewayCredentialUpdateBody) =>
    apiClient.patch<ProviderCredential>(`${GATEWAY_API_BASE}/my-credentials/${id}`, body),
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
  probeTeamCredential: (credentialId: string) =>
    apiClient.post<CredentialProbeResult>(
      `${GATEWAY_API_BASE}/credentials/${credentialId}/probe`,
      {}
    ),
  /** 基于探测结果批量导入到团队 GatewayModel */
  batchImportTeamModelsFromUpstream: (
    credentialId: string,
    body: TeamGatewayModelBatchImportBody
  ) =>
    apiClient.post<TeamGatewayModelBatchImportResponse>(
      `${GATEWAY_API_BASE}/credentials/${credentialId}/batch-import-models`,
      body
    ),

  /** 从用户配置文件（app.toml / .env）导入 system 凭据；返回新建条数 */
  importFromUserConfig: () =>
    apiClient.post<{ created: number }>(`${GATEWAY_API_BASE}/credentials/import`),
} as const
