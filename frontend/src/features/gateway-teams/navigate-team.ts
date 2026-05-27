/**
 * Gateway 团队切换：invalidate 查询 + 保留当前子路径导航。
 */

import type { QueryClient } from '@tanstack/react-query'
import type { Location, NavigateFunction } from 'react-router-dom'

const TEAM_PATH_RE = /^\/gateway\/teams\/[^/]+(\/.*)?$/

/** 从当前 Gateway 团队路径提取后缀（如 `/members`），默认 `/overview` */
export function gatewayTeamPathSuffix(pathname: string): string {
  const match = TEAM_PATH_RE.exec(pathname)
  return match?.[1] ?? '/overview'
}

export function switchGatewayTeam(
  teamId: string,
  navigate: NavigateFunction,
  location: Location,
  queryClient: QueryClient
): void {
  void queryClient.invalidateQueries({ queryKey: ['gateway'] })

  const match = TEAM_PATH_RE.exec(location.pathname)
  if (match) {
    navigate(`/gateway/teams/${teamId}${gatewayTeamPathSuffix(location.pathname)}`)
    return
  }
  navigate(`/gateway/teams/${teamId}/overview`)
}

/** 切换到 personal team；若无 personal 则选列表首项 */
export function switchToFallbackTeam(
  teams: ReadonlyArray<{ id: string; kind: string }>,
  navigate: NavigateFunction,
  location: Location,
  queryClient: QueryClient
): void {
  if (teams.length === 0) {
    navigate('/gateway/guide')
    return
  }
  const fallback = teams.find((t) => t.kind === 'personal') ?? teams[0]
  switchGatewayTeam(fallback.id, navigate, location, queryClient)
}
