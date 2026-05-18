/**
 * 上游批量导入：可导入项判断与统计。
 */

import type { CredentialUpstreamItem } from '@/api/gateway'

export function isImportableUpstreamItem(item: CredentialUpstreamItem): boolean {
  return item.already_registered !== true
}

export function countProbeItems(items: CredentialUpstreamItem[]): {
  total: number
  registered: number
  importable: number
} {
  const registered = items.filter((it) => it.already_registered).length
  return {
    total: items.length,
    registered,
    importable: items.length - registered,
  }
}

export function registeredLabel(item: CredentialUpstreamItem): string | null {
  if (!item.already_registered) return null
  const names = item.registered_names ?? []
  if (names.length === 0) return '已注册'
  if (names.length === 1) return `已注册 · ${names[0]}`
  return `已注册 · ${names[0]} 等 ${String(names.length)} 条`
}
