/**
 * 上游批量导入：可导入项判断与统计。
 */

import type { CredentialUpstreamItem } from '@/api/gateway'
import { resolveUpstreamModelTypes } from '@/features/gateway-models/infer-model-types'

export function isImportableUpstreamItem(item: CredentialUpstreamItem, provider = ''): boolean {
  if (item.already_registered === true) return false
  if (item.inferred_model_types !== undefined) {
    return item.inferred_model_types.length > 0
  }
  return resolveUpstreamModelTypes(item, provider).length > 0
}

export function countProbeItems(
  items: CredentialUpstreamItem[],
  provider = ''
): {
  total: number
  registered: number
  importable: number
} {
  const registered = items.filter((it) => it.already_registered).length
  const importable = items.filter((it) => isImportableUpstreamItem(it, provider)).length
  return {
    total: items.length,
    registered,
    importable,
  }
}

export function registeredLabel(item: CredentialUpstreamItem): string | null {
  if (!item.already_registered) return null
  const names = item.registered_names ?? []
  if (names.length === 0) return '已注册'
  if (names.length === 1) return `已注册 · ${names[0]}`
  return `已注册 · ${names[0]} 等 ${String(names.length)} 条`
}
