import type { GatewayTeam } from '@/api/gateway/teams'

/** 协作团队（排除 personal team / 个人工作区）；团队凭据 Tab 仅展示此类团队。 */
export function isCollaborationGatewayTeam(team: Pick<GatewayTeam, 'kind'>): boolean {
  return team.kind === 'shared'
}

export function filterCollaborationGatewayTeams(teams: readonly GatewayTeam[]): GatewayTeam[] {
  return teams.filter(isCollaborationGatewayTeam)
}
