/**
 * useGatewayPermission
 *
 * 基于平台 role + 当前 team_role 决策按钮可见性。
 * RBAC 矩阵参见 backend/AI Gateway 计划文档（plan §2.7）。
 */

import { useMemo } from 'react'

import { useGatewayTeamStore } from '@/stores/gateway-team'
import { useUserStore } from '@/stores/user'
import { TeamRole, type TeamRoleValue } from '@/types/permissions'

export const PlatformRole = {
  ADMIN: 'admin',
  USER: 'user',
  VIEWER: 'viewer',
} as const

export type PlatformRoleValue = (typeof PlatformRole)[keyof typeof PlatformRole]

export interface GatewayPermissionFlags {
  isAuthenticated: boolean
  isPlatformAdmin: boolean
  /** 平台只读账号（全站 Gateway 管理面不可写） */
  isPlatformViewer: boolean
  teamRole: TeamRoleValue | null
  /** 团队 owner */
  isOwner: boolean
  /** 平台 admin / 团队 admin / 团队 owner */
  isAdmin: boolean
  /** 团队 member 及以上 */
  isMember: boolean
  /** 是否可写（key/credential/model/route）：团队 admin+ 且非平台 viewer */
  canWrite: boolean
  /** 是否可看跨团队仪表盘：仅平台 admin */
  canViewCrossTeam: boolean
}

export function useGatewayPermission(): GatewayPermissionFlags {
  const { currentUser } = useUserStore()
  const teams = useGatewayTeamStore((s) => s.teams)
  const currentTeamId = useGatewayTeamStore((s) => s.currentTeamId)

  return useMemo(() => {
    const role = currentUser?.role as PlatformRoleValue | undefined
    const isPlatformAdmin = role === PlatformRole.ADMIN
    const isPlatformViewer = role === PlatformRole.VIEWER
    const team = teams.find((t) => t.id === currentTeamId) ?? null
    const teamRole = (team?.team_role as TeamRoleValue | null | undefined) ?? null
    const isOwner = teamRole === TeamRole.OWNER || isPlatformAdmin
    const isAdmin = isPlatformAdmin || teamRole === TeamRole.OWNER || teamRole === TeamRole.ADMIN
    const isMember = isAdmin || teamRole === TeamRole.MEMBER
    return {
      isAuthenticated: !(currentUser?.is_anonymous ?? true),
      isPlatformAdmin,
      isPlatformViewer,
      teamRole,
      isOwner,
      isAdmin,
      isMember,
      canWrite: isAdmin && !isPlatformViewer,
      canViewCrossTeam: isPlatformAdmin,
    }
  }, [currentUser, teams, currentTeamId])
}
