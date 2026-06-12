/**
 * 当 URL 中 teamId 不在 membership 列表时，回退到 personal / 首个可用团队。
 */

import { useEffect } from 'react'

import { useQueryClient } from '@tanstack/react-query'
import { useLocation, useNavigate } from 'react-router-dom'

import { switchToFallbackTeam } from '@/features/gateway-teams/navigate-team'
import { useGatewayMemberTeams } from '@/features/gateway-teams/use-gateway-teams'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useOptionalGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { useToast } from '@/hooks/use-toast'
import { useCurrentUser } from '@/stores/user'

const TEAM_ROUTE_RE = /^\/gateway\/teams\/([^/]+)/

/** 是否应将无效 teamId 回退（纯函数，便于单测） */
export function shouldRedirectInvalidGatewayTeamRoute(params: {
  routeTeamId: string | null
  teamsCount: number
  membershipTeamsReady: boolean
  isPlatformAdmin: boolean
  membershipTeamIds: ReadonlySet<string>
}): boolean {
  const { routeTeamId, teamsCount, membershipTeamsReady, isPlatformAdmin, membershipTeamIds } =
    params
  if (!routeTeamId || !membershipTeamsReady) return false
  // 与后端 TenancyManagementTeamResolveUseCase 对齐：平台 admin 可访问任意活跃团队
  if (isPlatformAdmin) return false
  if (teamsCount === 0) return true
  return !membershipTeamIds.has(routeTeamId)
}

/** 挂载于 GatewayLayout：修正 bookmark / 缓存中的无效 teamId。 */
export function useSyncGatewayTeamRoute(): void {
  const routeTeamId = useOptionalGatewayTeamId()
  const currentUser = useCurrentUser()
  const isAuthenticated = currentUser !== null
  const { isPlatformAdmin } = useGatewayPermission()
  const { data: memberTeams, isSuccess: membershipTeamsReady } =
    useGatewayMemberTeams(isAuthenticated)
  const navigate = useNavigate()
  const location = useLocation()
  const queryClient = useQueryClient()
  const { toast } = useToast()

  useEffect(() => {
    const teams = memberTeams ?? []
    const membershipTeamIds = new Set(teams.map((t) => t.id))
    if (
      !shouldRedirectInvalidGatewayTeamRoute({
        routeTeamId,
        teamsCount: teams.length,
        membershipTeamsReady,
        isPlatformAdmin,
        membershipTeamIds,
      })
    ) {
      return
    }

    switchToFallbackTeam(teams, navigate, location, queryClient)
    toast({
      title: '工作区不可用',
      description: '当前链接中的团队不存在或您无权访问，已切换到可用工作区。',
      variant: 'destructive',
    })
  }, [
    routeTeamId,
    memberTeams,
    membershipTeamsReady,
    isPlatformAdmin,
    navigate,
    location,
    queryClient,
    toast,
  ])
}

export function isGatewayTeamScopedPath(pathname: string): boolean {
  return TEAM_ROUTE_RE.test(pathname)
}
