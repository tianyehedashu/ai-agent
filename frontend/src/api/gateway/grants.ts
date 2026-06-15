/**
 * AI Gateway · 虚拟 Key 跨团队授权（Grants）
 *
 * 路径：`/teams/{teamId}/keys/{keyId}/grants`
 * 只有 vkey 创建者可管理授权。
 */

import { apiClient } from '@/api/client'

import { teamGatewayPath } from './_base'

/** 一条 active grant 行 */
export interface VirtualKeyTeamGrant {
  id: string
  vkey_id: string
  tenant_id: string
  /** 是否为 vkey 主属 team 的自洽行（不可撤销） */
  is_self: boolean
  created_at: string
  revoked_at: string | null
  /** 被授权 team 名称（后端附带） */
  granted_team_name: string | null
  /** 被授权 team slug（用于 model prefix 提示） */
  granted_team_slug: string | null
  /** 该 team 已注册 enabled 模型数 */
  model_count?: number
  /** 该 team 已注册模型名（enabled，升序） */
  registered_model_names?: string[]
}

/** 可授权候选 team */
export interface GrantableTeam {
  team_id: string
  name: string
  slug: string
  model_count?: number
}

/** POST /keys/{keyId}/grants body */
export interface VirtualKeyGrantBatchRequest {
  tenant_ids: string[]
}

/** Grants 资源 API */
export const grantsApi = {
  listGrants: (teamId: string, keyId: string) =>
    apiClient.get<VirtualKeyTeamGrant[]>(teamGatewayPath(teamId, `/keys/${keyId}/grants`)),
  grantToTeams: (teamId: string, keyId: string, body: VirtualKeyGrantBatchRequest) =>
    apiClient.post<VirtualKeyTeamGrant[]>(teamGatewayPath(teamId, `/keys/${keyId}/grants`), body),
  revokeGrant: (teamId: string, keyId: string, tenantId: string) =>
    apiClient.delete<unknown>(teamGatewayPath(teamId, `/keys/${keyId}/grants/${tenantId}`)),
  listGrantableTeams: (teamId: string, keyId: string) =>
    apiClient.get<GrantableTeam[]>(
      teamGatewayPath(teamId, `/keys/${keyId}/grants/grantable-teams`)
    ),
} as const
