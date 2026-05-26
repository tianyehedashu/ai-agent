/**
 * AI Gateway · 虚拟 Key（VKey）资源
 *
 * 虚拟 Key 是下游业务调用 Gateway 的凭证（`sk-gw-*`）。
 * 团队维度路径 `/teams/{teamId}/keys`；创建时返回明文，之后通过 `revealKey` 按需查看。
 * **外部 `/v1/*` 调用勿传 `X-Team-Id`**，团队已在 Key 创建时绑定。
 */

import { apiClient } from '@/api/client'

import { teamGatewayPath } from './_base'

/** 虚拟 Key 列表元数据（不含明文） */
export interface VirtualKey {
  id: string
  tenant_id?: string
  team_id: string
  name: string
  description?: string | null
  /** 形如 `sk-gw-***ab12` 的展示掩码，由后端生成 */
  masked_key: string
  allowed_models: string[]
  allowed_capabilities: string[]
  rpm_limit: number | null
  tpm_limit: number | null
  store_full_messages: boolean
  guardrail_enabled: boolean
  is_active: boolean
  /** 系统 Key（如平台占位 Key）；普通用户不可见、不可撤销 */
  is_system: boolean
  expires_at: string | null
  last_used_at: string | null
  usage_count: number
  created_at: string
}

/** 创建虚拟 Key 时随响应额外返回明文（仅本次） */
export interface VirtualKeyCreated extends VirtualKey {
  plain_key: string
}

/** 批量撤销时单条失败原因 */
export type VirtualKeyBatchRevokeReason = 'not_found' | 'permission_denied' | 'system_key'

export interface VirtualKeyBatchRevokeFailure {
  key_id: string
  reason: VirtualKeyBatchRevokeReason
}

/** POST /keys/revoke-batch 响应 */
export interface VirtualKeyBatchRevokeResult {
  revoked: string[]
  failed: VirtualKeyBatchRevokeFailure[]
}

export interface VirtualKeyCreateBody {
  name: string
  allowed_models?: string[]
  allowed_capabilities?: string[]
  rpm_limit?: number | null
  tpm_limit?: number | null
  store_full_messages?: boolean
  guardrail_enabled?: boolean
}

/** Keys 资源 API */
export const keysApi = {
  listKeys: (teamId: string) => apiClient.get<VirtualKey[]>(teamGatewayPath(teamId, '/keys')),
  createKey: (teamId: string, body: VirtualKeyCreateBody) =>
    apiClient.post<VirtualKeyCreated>(teamGatewayPath(teamId, '/keys'), body),
  revokeKey: (teamId: string, id: string) =>
    apiClient.delete<unknown>(teamGatewayPath(teamId, `/keys/${id}`)),
  revokeKeysBatch: (teamId: string, keyIds: string[]) =>
    apiClient.post<VirtualKeyBatchRevokeResult>(teamGatewayPath(teamId, '/keys/revoke-batch'), {
      key_ids: keyIds,
    }),
  revealKey: (teamId: string, id: string) =>
    apiClient.get<{ plain_key: string }>(teamGatewayPath(teamId, `/keys/${id}/reveal`)),
} as const
