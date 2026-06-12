/**
 * Gateway 凭据管理面权限（对齐 backend team_credential_access.py）。
 *
 * - canEditGatewayCredential：改/删/启用（创建者私有；legacy NULL + admin+）
 * - canLinkToCredentialDetail：详情深链（与可读集合一致）
 */

import type { CredentialSummary, ProviderCredential } from '@/api/gateway'
import type { GatewayTeam } from '@/api/gateway/teams'

export type CredentialOwnerFields = Pick<ProviderCredential, 'scope' | 'created_by_user_id'>

export type CredentialLinkScope = Pick<
  CredentialSummary,
  'scope' | 'created_by_user_id' | 'management_access'
>

export function isLegacySharedTeamCredential(cred: CredentialOwnerFields): boolean {
  return (
    cred.scope === 'team' &&
    (cred.created_by_user_id === null ||
      cred.created_by_user_id === undefined ||
      cred.created_by_user_id === '')
  )
}

export function actorOwnsTeamCredential(
  cred: CredentialOwnerFields,
  viewerUserId: string | null | undefined
): boolean {
  const creatorId = cred.created_by_user_id ?? null
  return (
    cred.scope === 'team' &&
    viewerUserId !== null &&
    viewerUserId !== undefined &&
    creatorId !== null &&
    creatorId === viewerUserId
  )
}

export function canEditGatewayCredential(
  c: ProviderCredential,
  viewerUserId: string | null | undefined,
  canWrite: boolean,
  isPlatformAdmin: boolean
): boolean {
  if (c.management_access === 'metadata') return false
  if (c.scope === 'system') return isPlatformAdmin
  if (c.scope !== 'team') return false
  if (actorOwnsTeamCredential(c, viewerUserId)) return true
  return isLegacySharedTeamCredential(c) && canWrite
}

/** 团队凭据：API 已过滤可见集合；system 仅平台管理员 */
export function canLinkToCredentialDetail(
  summary: CredentialLinkScope | undefined,
  viewerUserId: string | null | undefined,
  canWrite: boolean,
  isPlatformAdmin: boolean
): boolean {
  if (!summary) return false
  if ('management_access' in summary && summary.management_access === 'metadata') {
    return false
  }
  if (summary.scope === 'user') return false
  if (summary.scope === 'system') return isPlatformAdmin
  if (summary.scope !== 'team') return false

  const createdBy = summary.created_by_user_id ?? null
  if (actorOwnsTeamCredential({ scope: 'team', created_by_user_id: createdBy }, viewerUserId)) {
    return true
  }
  return isLegacySharedTeamCredential({ scope: 'team', created_by_user_id: createdBy }) && canWrite
}

export function canCreateTeamCredential(_team: Pick<GatewayTeam, 'kind'>): boolean {
  return _team.kind !== 'personal'
}

export function canManageSystemCredentialVisibility(isPlatformAdmin: boolean): boolean {
  return isPlatformAdmin
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

/** 注册模型时可绑定的 team 凭据（仅创建者 + legacy admin 可见集合） */
export function canBindCredentialForTeamModel(
  c: ProviderCredential,
  viewerUserId: string | null | undefined,
  canWrite: boolean
): boolean {
  if (c.scope !== 'team') return false
  if (actorOwnsTeamCredential(c, viewerUserId)) return true
  return isLegacySharedTeamCredential(c) && canWrite
}
