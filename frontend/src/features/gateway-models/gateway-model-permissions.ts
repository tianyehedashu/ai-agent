import type { GatewayModel } from '@/api/gateway'
import { CONFIG_MANAGED_BY } from '@/features/gateway-credentials/constants'

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

/** 团队模型：团队 admin+；系统模型：平台管理员 */
export function canManageGatewayModel(
  model: GatewayModel,
  canWrite: boolean,
  isPlatformAdmin: boolean,
  context?: GatewayModelPermissionContext
): boolean {
  if (resolveGatewayModelRegistryKind(model, context) === 'system') {
    return isPlatformAdmin
  }
  return canWrite || isPlatformAdmin
}

/** 系统 Tab 批量勾选：与 canDeleteGatewayModel 一致 */
export function isModelBatchSelectable(
  model: GatewayModel,
  canWrite: boolean,
  isPlatformAdmin: boolean,
  context?: GatewayModelPermissionContext
): boolean {
  return canDeleteGatewayModel(model, canWrite, isPlatformAdmin, context)
}

/** 团队模型：团队 admin+；系统模型：平台管理员且非配置托管 */
export function canDeleteGatewayModel(
  model: GatewayModel,
  canWrite: boolean,
  isPlatformAdmin: boolean,
  context?: GatewayModelPermissionContext
): boolean {
  if (resolveGatewayModelRegistryKind(model, context) === 'system') {
    return isPlatformAdmin && !isConfigManagedSystemModel(model, context)
  }
  return canWrite || isPlatformAdmin
}

/** 从 LiteLLM 同步能力：与 canDeleteGatewayModel 一致（config 托管不可 resync） */
export function canResyncGatewayModelCapabilities(
  model: GatewayModel,
  canWrite: boolean,
  isPlatformAdmin: boolean,
  context?: GatewayModelPermissionContext
): boolean {
  return canDeleteGatewayModel(model, canWrite, isPlatformAdmin, context)
}
