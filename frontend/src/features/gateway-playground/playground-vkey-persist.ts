/**
 * 试调虚拟 Key 选择持久化：旧版 localStorage 迁移（v1/v2/v3 明文缓存 → 仅 lastSelectedId）。
 * 生产读写经 `usePlaygroundVkeySelectionStore`（Zustand persist）。
 */

export const LEGACY_STORAGE_KEY_V3 = 'gateway:playground:vkey:v3'
export const LEGACY_STORAGE_KEYS = [
  'gateway:playground:vkey:v1',
  'gateway:playground:vkey:v2',
] as const

let legacyMigrationDone = false

/** 测试：允许重复执行迁移 */
export function resetPlaygroundVkeyLegacyMigration(): void {
  legacyMigrationDone = false
}

/** 一次性迁移旧缓存；可在 store rehydrate 或测试前调用。 */
export function migrateLegacyPlaygroundVkeyStorage(): string | null {
  if (typeof window === 'undefined') return null
  if (legacyMigrationDone) return null

  let migratedId: string | null = null

  try {
    const rawV3 = window.localStorage.getItem(LEGACY_STORAGE_KEY_V3)
    if (rawV3) {
      const parsed = JSON.parse(rawV3) as { v?: unknown; lastSelectedId?: unknown }
      if (parsed.v === 3) {
        if (typeof parsed.lastSelectedId === 'string') migratedId = parsed.lastSelectedId
        else if (parsed.lastSelectedId === null) migratedId = null
      }
      window.localStorage.removeItem(LEGACY_STORAGE_KEY_V3)
    }
  } catch {
    try {
      window.localStorage.removeItem(LEGACY_STORAGE_KEY_V3)
    } catch {
      // ignore
    }
  }

  for (const key of LEGACY_STORAGE_KEYS) {
    try {
      const raw = window.localStorage.getItem(key)
      if (!raw) continue
      const parsed = JSON.parse(raw) as {
        id?: unknown
        lastSelectedId?: unknown
        items?: unknown
      }
      if (typeof parsed.lastSelectedId === 'string') {
        migratedId ??= parsed.lastSelectedId
      } else if (typeof parsed.id === 'string') {
        migratedId ??= parsed.id
      } else if (Array.isArray(parsed.items) && parsed.items.length > 0) {
        const first = parsed.items[0] as { id?: unknown }
        if (typeof first.id === 'string') migratedId ??= first.id
      }
      window.localStorage.removeItem(key)
    } catch {
      try {
        window.localStorage.removeItem(key)
      } catch {
        // ignore
      }
    }
  }

  legacyMigrationDone = true
  return migratedId
}
