import type { GatewayTeam } from '@/api/gateway/teams'
import { isTeamAdminRole, isTeamMemberRole } from '@/types/permissions'

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

/**
 * 团队是否可由当前用户「贡献」创建者私有资源（团队凭据 / 自有凭据下的模型）。
 * 与后端 `POST /teams/{id}/credentials`（member+）对齐：任意成员均可创建，
 * 创建后归属为创建者私有。平台 viewer 全站只读，排除。
 */
export function isGatewayTeamContributor(
  team: GatewayTeam,
  isPlatformAdmin: boolean,
  isPlatformViewer: boolean
): boolean {
  if (isPlatformViewer) return false
  if (isPlatformAdmin) return true
  if (team.kind === 'personal') return true
  return isTeamMemberRole(team.team_role)
}

export function filterGatewayContributorTeams(
  teams: GatewayTeam[],
  isPlatformAdmin: boolean,
  isPlatformViewer: boolean
): GatewayTeam[] {
  return teams.filter((team) => isGatewayTeamContributor(team, isPlatformAdmin, isPlatformViewer))
}
