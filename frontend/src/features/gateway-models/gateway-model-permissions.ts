import type { GatewayModel } from '@/api/gateway'
import { CONFIG_MANAGED_BY } from '@/features/gateway-credentials/constants'

export function isConfigManagedSystemModel(model: GatewayModel): boolean {
  if (model.registry_kind !== 'system') return false
  return model.tags?.managed_by === CONFIG_MANAGED_BY
}

/** 团队模型：团队 admin+；系统模型：平台管理员 */
export function canManageGatewayModel(
  model: GatewayModel,
  canWrite: boolean,
  isPlatformAdmin: boolean
): boolean {
  if (model.registry_kind === 'system') {
    return isPlatformAdmin
  }
  return canWrite
}

/** 团队模型：团队 admin+；系统模型：平台管理员且非配置托管 */
export function canDeleteGatewayModel(
  model: GatewayModel,
  canWrite: boolean,
  isPlatformAdmin: boolean
): boolean {
  if (model.registry_kind === 'system') {
    return isPlatformAdmin && !isConfigManagedSystemModel(model)
  }
  return canWrite
}
