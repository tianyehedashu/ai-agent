/**
 * 登录后拉取 membership 团队列表并写入 gateway-team store（无 UI）。
 */

import { useEffect } from 'react'

import type { GatewayTeam as ApiGatewayTeam } from '@/api/gateway/teams'
import { useGatewayMemberTeams } from '@/features/gateway-teams/use-gateway-teams'
import { useGatewayTeamStore, type GatewayTeam } from '@/stores/gateway-team'
import { useUserStore } from '@/stores/user'

function toStoreTeam(team: ApiGatewayTeam): GatewayTeam {
  return {
    id: team.id,
    name: team.name,
    slug: team.slug,
    kind: team.kind,
    team_role: team.team_role,
  }
}

/** 挂载于 Layout：未登录跳过；已登录用户注水 teams 缓存 */
export function useHydrateGatewayTeamStore(): void {
  const isAuthenticated = useUserStore((s) => s.currentUser !== null)
  const setTeams = useGatewayTeamStore((s) => s.setTeams)
  const { data: teams } = useGatewayMemberTeams(isAuthenticated)

  useEffect(() => {
    if (!teams) return
    setTeams(teams.map(toStoreTeam))
  }, [teams, setTeams])
}
