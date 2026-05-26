import type { GatewayTeam } from '@/api/gateway/teams'
import { isTeamAdminRole, teamRoleLabel } from '@/types/permissions'

export function gatewayTeamDisplayLabel(team: GatewayTeam): string {
  return team.kind === 'personal' ? '个人工作区' : team.name
}

export function gatewayTeamCommandItemValue(team: GatewayTeam): string {
  return `${team.name} ${team.slug}`
}

/** 列表项角色副标题；平台 admin 对非 admin 成员身份的团队标注「平台」旁路。 */
export function gatewayTeamRoleSubtitle(team: GatewayTeam, isPlatformAdmin = false): string {
  if (team.kind === 'personal') return '个人'
  if (isPlatformAdmin && !isTeamAdminRole(team.team_role)) return '平台'
  return teamRoleLabel(team.team_role ?? 'member')
}
