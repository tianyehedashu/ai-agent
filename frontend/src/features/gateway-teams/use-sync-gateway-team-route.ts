/**
 * 当 URL 中 teamId 不在 membership 列表时，回退到 personal / 首个可用团队。
 */

import { useEffect } from 'react'

import { useQueryClient } from '@tanstack/react-query'
import { useLocation, useNavigate } from 'react-router-dom'

import { switchToFallbackTeam } from '@/features/gateway-teams/navigate-team'
import {
  useGatewayMembershipTeamIdSet,
  useOptionalGatewayTeamId,
} from '@/hooks/use-gateway-team-id'
import { useToast } from '@/hooks/use-toast'
import { useGatewayTeamStore } from '@/stores/gateway-team'

const TEAM_ROUTE_RE = /^\/gateway\/teams\/([^/]+)/

/** 挂载于 GatewayLayout：修正 bookmark / 缓存中的无效 teamId。 */
export function useSyncGatewayTeamRoute(): void {
  const routeTeamId = useOptionalGatewayTeamId()
  const membershipTeamIds = useGatewayMembershipTeamIdSet()
  const teams = useGatewayTeamStore((s) => s.teams)
  const navigate = useNavigate()
  const location = useLocation()
  const queryClient = useQueryClient()
  const { toast } = useToast()

  useEffect(() => {
    if (!routeTeamId || teams.length === 0) return
    if (membershipTeamIds.has(routeTeamId)) return

    switchToFallbackTeam(teams, navigate, location, queryClient)
    toast({
      title: '工作区不可用',
      description: '当前链接中的团队不存在或您无权访问，已切换到可用工作区。',
      variant: 'destructive',
    })
  }, [routeTeamId, teams, membershipTeamIds, navigate, location, queryClient, toast])
}

export function isGatewayTeamScopedPath(pathname: string): boolean {
  return TEAM_ROUTE_RE.test(pathname)
}
