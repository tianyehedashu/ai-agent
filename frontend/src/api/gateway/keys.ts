/**
 * AI Gateway · 虚拟 Key（VKey）资源
 *
 * 虚拟 Key 是下游业务调用 Gateway 的凭证（`sk-gw-*`）。
 * 列表与撤销在 X-Team-Id 维度生效；明文仅创建时返回一次，按需 `reveal`。
 */

import { apiClient } from '@/api/client'

import { GATEWAY_API_BASE } from './_base'

/** 虚拟 Key 列表元数据（不含明文） */
export interface VirtualKey {
  id: string
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
  /** 列出当前团队下可见的虚拟 Key（不含 system / 已撤销 ≈ inactive） */
  listKeys: () => apiClient.get<VirtualKey[]>(`${GATEWAY_API_BASE}/keys`),
  /** 创建虚拟 Key；响应含 `plain_key`，仅本次可见 */
  createKey: (body: VirtualKeyCreateBody) =>
    apiClient.post<VirtualKeyCreated>(`${GATEWAY_API_BASE}/keys`, body),
  /** 撤销单条虚拟 Key（不可恢复） */
  revokeKey: (id: string) => apiClient.delete<unknown>(`${GATEWAY_API_BASE}/keys/${id}`),
  /** 批量撤销虚拟 Key；返回 revoked 与 failed 明细 */
  revokeKeysBatch: (keyIds: string[]) =>
    apiClient.post<VirtualKeyBatchRevokeResult>(`${GATEWAY_API_BASE}/keys/revoke-batch`, {
      key_ids: keyIds,
    }),
  /** 重新揭示 Key 明文（要求 owner / admin 权限；服务端记录审计日志） */
  revealKey: (id: string) =>
    apiClient.get<{ plain_key: string }>(`${GATEWAY_API_BASE}/keys/${id}/reveal`),
} as const
