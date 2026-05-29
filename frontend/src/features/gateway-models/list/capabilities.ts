import { SYSTEM_BROWSE_CAPABILITIES } from './list-presets'

import type { GatewayModelListCapabilities, GatewayModelListPermissionContext } from './types'

/**
 * 仅 admin+（`canWrite`）可用：跨「当前筛选」批量操作，会触及他人模型，
 * 不能下放给创建者私有成员。
 */
const ADMIN_GATED_KEYS = [
  'deleteAllFiltered',
] as const satisfies readonly (keyof GatewayModelListCapabilities)[]

/**
 * 贡献者（member+，`canContribute`）即可启用的能力；行级/勾选归属仍由
 * Row callback（canManage / canDelete / canBatchSelect）裁剪到「自有模型」。
 */
const CONTRIBUTOR_GATED_KEYS = [
  'batchSelect',
  'batchTest',
  'batchResync',
  'batchDelete',
  'deleteFailed',
  'rowToggleEnabled',
  'rowDelete',
] as const satisfies readonly (keyof GatewayModelListCapabilities)[]

/** preset + 权限 → 实际渲染能力（行级 gate 由 Row callback 二次裁剪） */
export function effectiveCapabilities(
  preset: GatewayModelListCapabilities,
  perm: GatewayModelListPermissionContext
): GatewayModelListCapabilities {
  if (preset.variant === 'readonly' || preset.variant === 'embedded') {
    return preset
  }

  if (preset.scope === 'system' && !perm.isPlatformAdmin) {
    return SYSTEM_BROWSE_CAPABILITIES
  }

  // 兼容仅管理员场景：未显式提供 canContribute 时回退到 canWrite。
  const canContribute = perm.canContribute ?? perm.canWrite
  if (perm.canWrite && canContribute) {
    return preset
  }

  const gated: GatewayModelListCapabilities = { ...preset }
  if (!canContribute) {
    for (const key of CONTRIBUTOR_GATED_KEYS) {
      gated[key] = false
    }
  }
  if (!perm.canWrite) {
    for (const key of ADMIN_GATED_KEYS) {
      gated[key] = false
    }
  }
  return gated
}
