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

/** 团队角色中文展示 */
export function teamRoleLabel(role: string): string {
  switch (role) {
    case TeamRole.OWNER:
      return '所有者'
    case TeamRole.ADMIN:
      return '管理员'
    case TeamRole.MEMBER:
      return '成员'
    default:
      return role
  }
}

/** 成员主/副标题（优先姓名与邮箱，回退 UUID 前缀） */
export function formatTeamMemberDisplay(member: {
  user_id: string
  role: string
  user_email?: string | null
  user_name?: string | null
}): { primary: string; secondary: string } {
  const role = teamRoleLabel(member.role)
  const name = member.user_name?.trim()
  const email = member.user_email?.trim()

  if (name && email) {
    return { primary: name, secondary: `${email} · ${role}` }
  }
  if (email) {
    return { primary: email, secondary: role }
  }
  if (name) {
    return { primary: name, secondary: role }
  }
  return { primary: `${member.user_id.slice(0, 8)}…`, secondary: role }
}
