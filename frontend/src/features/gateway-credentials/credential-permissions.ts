/**
 * Gateway 凭据管理面权限（对齐 backend managed_team_credentials_policy、gateway_admin.py）。
 *
 * - canEditGatewayCredential：改/删/启用（canWrite + scope）
 * - canLinkToCredentialDetail：详情深链（isAdmin；platform viewer 团队 admin 可读详情）
 */

import type { CredentialSummary, ProviderCredential } from '@/api/gateway'
import type { GatewayTeam } from '@/api/gateway/teams'

export type CredentialTableViewMode = 'current-team' | 'cross-team'

type CredentialLinkScope = Pick<CredentialSummary, 'scope'> | Pick<ProviderCredential, 'scope'>

export function canEditGatewayCredential(
  c: ProviderCredential,
  canWrite: boolean,
  isPlatformAdmin: boolean
): boolean {
  return (c.scope === 'team' && canWrite) || (c.scope === 'system' && isPlatformAdmin)
}

/** 团队 admin+ 可打开团队凭据详情；system 凭据仅平台管理员；个人 BYOK 无团队详情页 */
export function canLinkToCredentialDetail(
  summary: CredentialLinkScope | undefined,
  isAdmin: boolean,
  isPlatformAdmin: boolean
): boolean {
  if (!summary || !isAdmin) return false
  if (summary.scope === 'user') return false
  if (summary.scope === 'system') return isPlatformAdmin
  return true
}

export function canViewCrossTeamCredentialsOverview(
  canWrite: boolean,
  writableTeamCount: number
): boolean {
  return canWrite && writableTeamCount > 1
}

export function canManageSystemCredentialVisibility(isPlatformAdmin: boolean): boolean {
  return isPlatformAdmin
}

export function shouldShowTeamAffiliationColumn(
  viewMode: CredentialTableViewMode,
  writableTeamCount: number
): boolean {
  if (viewMode === 'cross-team') return true
  return writableTeamCount > 1
}

export function isWritableTargetTeam(
  teamId: string,
  writableTeams: readonly GatewayTeam[]
): boolean {
  return writableTeams.some((team) => team.id === teamId)
}

/** 列表/详情深链使用的团队上下文：跨团队视图用凭据归属 tenant_id */
export function credentialDetailTeamId(
  cred: Pick<ProviderCredential, 'tenant_id' | 'scope'>,
  routeTeamId: string
): string {
  if (cred.scope === 'team' && cred.tenant_id) {
    return cred.tenant_id
  }
  return routeTeamId
}
