/**
 * 凭据作用域 / 归属 / 可见性文案（无 JSX，供 Playground 等复用）。
 */

import type { ProviderCredential } from '@/api/gateway'
import { resolveGatewayTeamLabel } from '@/features/gateway-teams/use-gateway-teams'

export const CREDENTIAL_SCOPE_LABELS: Record<'user' | 'team' | 'system', string> = {
  user: '个人',
  team: '团队',
  system: '系统',
}

export function credentialScopeLabel(scope: 'user' | 'team' | 'system' | null | undefined): string {
  if (scope === 'user' || scope === 'team' || scope === 'system') {
    return CREDENTIAL_SCOPE_LABELS[scope]
  }
  return '—'
}

export function credentialTeamLabel(
  tenantId: string | null | undefined,
  teamNameById: Map<string, string>
): string {
  if (!tenantId) return '—'
  return resolveGatewayTeamLabel(teamNameById, tenantId)
}

export function systemVisibilityLabel(visibility: ProviderCredential['visibility']): string {
  if (visibility === 'restricted') return '受限'
  if (visibility === 'public') return '公开'
  return '公开'
}
