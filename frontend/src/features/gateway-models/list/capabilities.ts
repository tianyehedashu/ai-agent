import { SYSTEM_BROWSE_CAPABILITIES } from './list-presets'

import type { GatewayModelListCapabilities, GatewayModelListPermissionContext } from './types'

const WRITE_GATED_KEYS = [
  'batchSelect',
  'batchTest',
  'batchResync',
  'batchDelete',
  'deleteAllFiltered',
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

  if (!perm.canWrite) {
    const gated: GatewayModelListCapabilities = { ...preset }
    for (const key of WRITE_GATED_KEYS) {
      gated[key] = false
    }
    return gated
  }

  return preset
}
