import type { GatewayModel } from '@/api/gateway'
import { CONFIG_MANAGED_BY } from '@/features/gateway-credentials/constants'
import { actorOwnsTeamCredential } from '@/features/gateway-credentials/credential-permissions'

export interface GatewayModelPermissionContext {
  /** 当前在系统模型 Tab / 深链 `?tab=system` 时为 true */
  preferSystem?: boolean
}

/** 解析注册表归属；API 缺字段时按 tenant / visibility 等启发式补全 */
export function resolveGatewayModelRegistryKind(
  model: GatewayModel,
  context?: GatewayModelPermissionContext
): 'team' | 'system' {
  if (model.registry_kind === 'system' || model.registry_kind === 'team') {
    return model.registry_kind
  }
  if (context?.preferSystem) {
    return 'system'
  }
  if (typeof model.tenant_id === 'string' || model.team_id !== null) {
    return 'team'
  }
  if (model.visibility !== null && model.visibility !== undefined) {
    return 'system'
  }
  if (model.system_credential !== null && model.system_credential !== undefined) {
    return 'system'
  }
  return 'team'
}

export function isConfigManagedSystemModel(
  model: GatewayModel,
  context?: GatewayModelPermissionContext
): boolean {
  if (resolveGatewayModelRegistryKind(model, context) !== 'system') return false
  return model.tags?.managed_by === CONFIG_MANAGED_BY
}

function teamCredentialOwnerId(model: GatewayModel): string | null | undefined {
  return model.credential_created_by_user_id
}

function isLegacyTeamModel(model: GatewayModel): boolean {
  const ownerId = teamCredentialOwnerId(model)
  return ownerId === null || ownerId === undefined || ownerId === ''
}

function actorOwnsTeamModel(model: GatewayModel, viewerUserId: string | null | undefined): boolean {
  const ownerId = teamCredentialOwnerId(model)
  if (ownerId === null || ownerId === undefined || ownerId === '') return false
  return (
    viewerUserId !== null &&
    viewerUserId !== undefined &&
    actorOwnsTeamCredential({ scope: 'team', created_by_user_id: ownerId }, viewerUserId)
  )
}

function actorCreatedModel(model: GatewayModel, viewerUserId: string | null | undefined): boolean {
  const creatorId = model.created_by_user_id
  if (creatorId === null || creatorId === undefined || creatorId === '') return false
  return viewerUserId !== null && viewerUserId !== undefined && viewerUserId === creatorId
}

/** 团队模型：凭据 owner、模型创建者或 legacy admin+；系统模型：平台管理员 */
export function canManageGatewayModel(
  model: GatewayModel,
  viewerUserId: string | null | undefined,
  canWrite: boolean,
  isPlatformAdmin: boolean,
  context?: GatewayModelPermissionContext
): boolean {
  if (resolveGatewayModelRegistryKind(model, context) === 'system') {
    return isPlatformAdmin
  }
  if (actorOwnsTeamModel(model, viewerUserId)) return true
  if (actorCreatedModel(model, viewerUserId)) return true
  if (isLegacyTeamModel(model) && canWrite) return true
  return false
}

/** 系统 Tab 批量勾选：与 canDeleteGatewayModel 一致 */
export function isModelBatchSelectable(
  model: GatewayModel,
  viewerUserId: string | null | undefined,
  canWrite: boolean,
  isPlatformAdmin: boolean,
  context?: GatewayModelPermissionContext
): boolean {
  return canDeleteGatewayModel(model, viewerUserId, canWrite, isPlatformAdmin, context)
}

/** 团队模型：owner 或 team admin（含 legacy admin+）；系统模型：平台管理员且非配置托管 */
export function canDeleteGatewayModel(
  model: GatewayModel,
  viewerUserId: string | null | undefined,
  canWrite: boolean,
  isPlatformAdmin: boolean,
  context?: GatewayModelPermissionContext
): boolean {
  if (resolveGatewayModelRegistryKind(model, context) === 'system') {
    return isPlatformAdmin && !isConfigManagedSystemModel(model, context)
  }
  if (actorOwnsTeamModel(model, viewerUserId)) return true
  if (actorCreatedModel(model, viewerUserId)) return true
  if (isLegacyTeamModel(model) && canWrite) return true
  if (canWrite && !isLegacyTeamModel(model)) return true
  return false
}

/** 从 LiteLLM 同步能力：与 canManageGatewayModel 一致 */
export function canResyncGatewayModelCapabilities(
  model: GatewayModel,
  viewerUserId: string | null | undefined,
  canWrite: boolean,
  isPlatformAdmin: boolean,
  context?: GatewayModelPermissionContext
): boolean {
  return canManageGatewayModel(model, viewerUserId, canWrite, isPlatformAdmin, context)
}

/** member+ 可尝试注册团队模型（具体凭据绑定仍受 canBindCredentialForTeamModel 约束） */
export function canRegisterTeamGatewayModel(): boolean {
  return true
}
