/**
 * useGatewayPermission
 *
 * 基于平台 role + 当前 team_role 决策按钮可见性。
 * RBAC 矩阵参见 backend/AI Gateway 计划文档（plan §2.7）。
 */

import { useMemo } from 'react'

import { useGatewayTeamStore } from '@/stores/gateway-team'
import { useUserStore } from '@/stores/user'

export interface GatewayPermissionFlags {
  isAuthenticated: boolean
  isPlatformAdmin: boolean
  teamRole: 'owner' | 'admin' | 'member' | null
  /** 团队 owner */
  isOwner: boolean
  /** 平台 admin / 团队 admin / 团队 owner */
  isAdmin: boolean
  /** 团队 member 及以上 */
  isMember: boolean
  /** 是否可写（key/credential/model/route）：admin 及以上 */
  canWrite: boolean
  /** 是否可看跨团队仪表盘：仅平台 admin */
  canViewCrossTeam: boolean
}

export function useGatewayPermission(): GatewayPermissionFlags {
  const { currentUser } = useUserStore()
  const teams = useGatewayTeamStore((s) => s.teams)
  const currentTeamId = useGatewayTeamStore((s) => s.currentTeamId)

  return useMemo(() => {
    const role = currentUser?.role
    const isPlatformAdmin = role === 'admin'
    const team = teams.find((t) => t.id === currentTeamId) ?? null
    const teamRole = (team?.team_role as 'owner' | 'admin' | 'member' | null | undefined) ?? null
    const isOwner = teamRole === 'owner' || isPlatformAdmin
    const isAdmin = isPlatformAdmin || teamRole === 'owner' || teamRole === 'admin'
    const isMember = isAdmin || teamRole === 'member'
    return {
      isAuthenticated: !(currentUser?.is_anonymous ?? true),
      isPlatformAdmin,
      teamRole,
      isOwner,
      isAdmin,
      isMember,
      canWrite: isAdmin,
      canViewCrossTeam: isPlatformAdmin,
    }
  }, [currentUser, teams, currentTeamId])
}
