/**
 * 与后端团队角色 / Gateway 权限矩阵对齐（见 backend/docs/项目权限规则.md）。
 */
export const TeamRole = {
  OWNER: 'owner',
  ADMIN: 'admin',
  MEMBER: 'member',
} as const

export type TeamRoleValue = (typeof TeamRole)[keyof typeof TeamRole]

export function isTeamAdminRole(role: string | null | undefined): boolean {
  return role === TeamRole.OWNER || role === TeamRole.ADMIN
}

export function isTeamMemberRole(role: string | null | undefined): boolean {
  return role === TeamRole.OWNER || role === TeamRole.ADMIN || role === TeamRole.MEMBER
}
