/**
 * AI Gateway · 团队（Team）资源
 *
 * 团队是 Gateway 多租户与权限的最小边界；团队资源经 URL 路径 `/teams/{teamId}/*` 显式选团队。
 * 团队详情包含 personal / shared 两类；personal 即「我的工作区」。
 */

import { apiClient } from '@/api/client'
import type { PaginatedList } from '@/types'

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
  owner_email?: string | null
  owner_name?: string | null
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
  user_email?: string | null
  user_name?: string | null
}

/** 按邮箱查找用户（团队 admin 添加成员前） */
export interface TeamMemberLookup {
  id: string
  email: string
  name: string | null
}

/** 可邀请用户（与 TeamMemberLookup 字段一致） */
export type TeamInviteCandidate = TeamMemberLookup

export type InviteCandidateScope = 'all_users' | 'shared_teams'

export interface ListTeamInviteCandidatesParams {
  search?: string
  page: number
  page_size?: number
}

export type TeamInviteCandidateListResponse = PaginatedList<TeamInviteCandidate>

/** GET /teams 可选 query */
export interface ListGatewayTeamsParams {
  search?: string
  membership_only?: boolean
  /** 平台 admin 全站列表是否包含匿名 personal team（默认 false） */
  include_anonymous_personal?: boolean
}

/** Teams 资源 API */
export const teamsApi = {
  /** 列出团队：普通用户为 membership；平台 admin 为全部活跃团队（可用 search 过滤） */
  listTeams: (params?: ListGatewayTeamsParams) =>
    apiClient.get<GatewayTeam[]>(`${GATEWAY_API_BASE}/teams`, {
      search: params?.search,
      membership_only: params?.membership_only,
      include_anonymous_personal: params?.include_anonymous_personal,
    }),
  /** 创建共享团队（personal 团队由后端自动 provisioning） */
  createTeam: (body: { name: string; slug?: string }) =>
    apiClient.post<GatewayTeam>(`${GATEWAY_API_BASE}/teams`, body),
  /** 更新团队（仅 admin+） */
  updateTeam: (id: string, body: { name?: string; settings?: Record<string, unknown> }) =>
    apiClient.patch<GatewayTeam>(`${GATEWAY_API_BASE}/teams/${id}`, body),
  /** 删除团队（仅 owner） */
  deleteTeam: (id: string) => apiClient.delete<unknown>(`${GATEWAY_API_BASE}/teams/${id}`),
  /** 列出指定团队成员 */
  listMembers: (teamId: string) => apiClient.get<TeamMember[]>(teamGatewayPath(teamId, '/members')),
  /** 按邮箱查找已注册用户（仅 admin+） */
  lookupMemberByEmail: (teamId: string, email: string) =>
    apiClient.get<TeamMemberLookup>(teamGatewayPath(teamId, '/members/lookup'), { email }),
  /** 分页列出可邀请用户（仅 admin+） */
  listInviteCandidates: (teamId: string, params: ListTeamInviteCandidatesParams) =>
    apiClient.get<TeamInviteCandidateListResponse>(teamGatewayPath(teamId, '/members/candidates'), {
      search: params.search,
      page: params.page,
      page_size: params.page_size,
    }),
  /** 添加成员（仅 owner / admin） */
  addMember: (teamId: string, body: { user_id: string; role: string }) =>
    apiClient.post<TeamMember>(teamGatewayPath(teamId, '/members'), body),
  /** 当前用户退出团队 */
  leaveTeam: (teamId: string) => apiClient.delete<unknown>(teamGatewayPath(teamId, '/members/me')),
  /** 移除成员（仅 owner / admin；不可移除自己） */
  removeMember: (teamId: string, userId: string) =>
    apiClient.delete<unknown>(teamGatewayPath(teamId, `/members/${userId}`)),
} as const
