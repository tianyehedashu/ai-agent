import type { GatewayTeam } from '@/api/gateway/teams'
import { isTeamAdminRole } from '@/types/permissions'

/** 团队是否可在 Gateway 管理面写入（凭据/模型/Key 等），与后端 is_team_admin_or_platform 对齐。 */
export function isGatewayTeamWritable(team: GatewayTeam, isPlatformAdmin: boolean): boolean {
  if (isPlatformAdmin) return true
  if (team.kind === 'personal') return true
  return isTeamAdminRole(team.team_role)
}

export function filterGatewayWritableTeams(
  teams: GatewayTeam[],
  isPlatformAdmin: boolean
): GatewayTeam[] {
  return teams.filter((team) => isGatewayTeamWritable(team, isPlatformAdmin))
}
