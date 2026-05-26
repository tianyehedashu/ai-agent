import type { GatewayTeam } from '@/api/gateway/teams'
import { isTeamAdminRole, teamRoleLabel } from '@/types/permissions'

export interface GatewayTeamDisplayOptions {
  /** 当前登录用户 id；用于区分「我的工作区」vs 他人 personal team */
  viewerUserId?: string | null
}

function foreignPersonalTeamLabel(team: GatewayTeam): string {
  const ownerHint = team.owner_email ?? team.owner_name ?? `${team.owner_user_id.slice(0, 8)}…`
  return `个人 · ${ownerHint}`
}

export function gatewayTeamDisplayLabel(
  team: GatewayTeam,
  options?: GatewayTeamDisplayOptions
): string {
  if (team.kind === 'personal') {
    const viewerId = options?.viewerUserId
    if (viewerId && team.owner_user_id !== viewerId) {
      return foreignPersonalTeamLabel(team)
    }
    return '个人工作区'
  }
  return team.name
}

export function gatewayTeamCommandItemValue(team: GatewayTeam): string {
  return `${team.name} ${team.slug}`
}

/**
 * 团队凭据 Tab 内「跨团队汇总」切换按钮文案。
 * 平台 admin 可见全部活跃团队，不在按钮上展示巨大数字；具体数量在汇总视图说明中展示。
 */
export function gatewayCrossTeamOverviewTabLabel(
  writableTeamCount: number,
  isPlatformAdmin: boolean
): string {
  if (isPlatformAdmin) return '全平台汇总'
  return `全部可管理 (${String(writableTeamCount)})`
}

/** 列表项角色副标题；平台 admin 对非 admin 成员身份的团队标注「平台」旁路。 */
export function gatewayTeamRoleSubtitle(team: GatewayTeam, isPlatformAdmin = false): string {
  if (team.kind === 'personal') return '个人'
  if (isPlatformAdmin && !isTeamAdminRole(team.team_role)) return '平台'
  return teamRoleLabel(team.team_role ?? 'member')
}
