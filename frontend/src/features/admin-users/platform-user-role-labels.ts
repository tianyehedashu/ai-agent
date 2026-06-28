import type { PlatformRole } from '@/api/admin-users'

export const PLATFORM_ROLE_LABELS: Record<PlatformRole, string> = {
  admin: '平台管理员',
  user: '普通用户',
  viewer: '只读账号',
}

export function platformRoleLabel(role: string): string {
  if (role in PLATFORM_ROLE_LABELS) {
    return PLATFORM_ROLE_LABELS[role as PlatformRole]
  }
  return role
}
