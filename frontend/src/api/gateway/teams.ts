/**
 * AI Gateway · 团队（Team）资源
 *
 * 团队是 Gateway 多租户与权限的最小边界；团队资源经 URL 路径 `/teams/{teamId}/*` 显式选团队。
 * 团队详情包含 personal / shared 两类；personal 即「我的工作区」。
 */

import { apiClient } from '@/api/client'

import { GATEWAY_API_BASE, teamGatewayPath } from './_base'

/**
 * Gateway 团队元数据（与后端 schemas/common.py `GatewayTeam` 对齐）。
 *
 * - `kind=personal`：当前用户的私人工作区；后端为每个用户自动 provisioning
 * - `kind=shared`：受邀加入的协作团队
 */
export interface GatewayTeam {
  id: string
  name: string
  slug: string
  kind: 'personal' | 'shared'
  owner_user_id: string
  /** 后端扩展角色时用 string；常见值 owner | admin | member */
  team_role?: string | null
  is_active?: boolean
  settings?: Record<string, unknown> | null
  created_at?: string
}

/** 团队成员（owner / admin / member） */
export interface TeamMember {
  id: string
  team_id: string
  user_id: string
  role: string
  created_at: string
}

/** Teams 资源 API */
export const teamsApi = {
  /** 列出当前用户可见的全部团队（含 personal + shared） */
  listTeams: () => apiClient.get<GatewayTeam[]>(`${GATEWAY_API_BASE}/teams`),
  /** 创建共享团队（personal 团队由后端自动 provisioning） */
  createTeam: (body: { name: string; slug?: string }) =>
    apiClient.post<GatewayTeam>(`${GATEWAY_API_BASE}/teams`, body),
  /** 删除团队（仅 owner） */
  deleteTeam: (id: string) => apiClient.delete<unknown>(`${GATEWAY_API_BASE}/teams/${id}`),
  /** 列出指定团队成员 */
  listMembers: (teamId: string) => apiClient.get<TeamMember[]>(teamGatewayPath(teamId, '/members')),
  /** 添加成员（仅 owner / admin） */
  addMember: (teamId: string, body: { user_id: string; role: string }) =>
    apiClient.post<TeamMember>(teamGatewayPath(teamId, '/members'), body),
  /** 移除成员（仅 owner / admin；不可移除自己） */
  removeMember: (teamId: string, userId: string) =>
    apiClient.delete<unknown>(teamGatewayPath(teamId, `/members/${userId}`)),
} as const
