/**
 * 按团队名称 / slug 筛选可写团队（跨团队分组列表客户端筛选）。
 */

import type { GatewayTeam } from '@/api/gateway/teams'
import { gatewayTeamDisplayLabel } from '@/features/gateway-teams/gateway-team-display'

export function filterWritableTeamsBySearch(
  teams: readonly GatewayTeam[],
  search: string,
  viewerUserId?: string | null
): GatewayTeam[] {
  const query = search.trim().toLowerCase()
  if (!query) return [...teams]

  return teams.filter((team) => {
    const label = gatewayTeamDisplayLabel(team, { viewerUserId }).toLowerCase()
    return (
      label.includes(query) ||
      team.name.toLowerCase().includes(query) ||
      team.slug.toLowerCase().includes(query)
    )
  })
}
