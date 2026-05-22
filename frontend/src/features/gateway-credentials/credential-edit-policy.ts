/**
 * 团队/系统凭据是否可在管理面编辑（列表、详情共用）。
 */

import type { ProviderCredential } from '@/api/gateway'

export function canEditGatewayCredential(
  c: ProviderCredential,
  canWrite: boolean,
  isPlatformAdmin: boolean
): boolean {
  return (c.scope === 'team' && canWrite) || (c.scope === 'system' && isPlatformAdmin)
}
