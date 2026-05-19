/**
 * 试调页虚拟 Key 上次选中 id（仅 id，不存明文）。
 */

import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'

import {
  LEGACY_STORAGE_KEY_V3,
  LEGACY_STORAGE_KEYS,
  migrateLegacyPlaygroundVkeyStorage,
} from '@/features/gateway-playground/playground-vkey-persist'

interface PlaygroundVkeySelectionState {
  lastSelectedId: string | null
  setLastSelectedId: (id: string | null) => void
}

export const PLAYGROUND_VKEY_SELECTION_STORAGE_KEY = 'gateway-playground-vkey-selection'

export const usePlaygroundVkeySelectionStore = create<PlaygroundVkeySelectionState>()(
  persist(
    (set) => ({
      lastSelectedId: null,
      setLastSelectedId: (id) => {
        set({ lastSelectedId: id })
      },
    }),
    {
      name: PLAYGROUND_VKEY_SELECTION_STORAGE_KEY,
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({ lastSelectedId: state.lastSelectedId }),
      onRehydrateStorage: () => {
        const migratedId = migrateLegacyPlaygroundVkeyStorage()
        return (state) => {
          if (migratedId !== null && state?.lastSelectedId === null) {
            state.setLastSelectedId(migratedId)
          }
        }
      },
    }
  )
)

/** 测试用：读取 persist 中的 lastSelectedId */
export function readPersistedPlaygroundVkeySelection(): string | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = window.localStorage.getItem(PLAYGROUND_VKEY_SELECTION_STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as { state?: { lastSelectedId?: unknown } }
    const id = parsed.state?.lastSelectedId
    return typeof id === 'string' ? id : id === null ? null : null
  } catch {
    return null
  }
}

export { LEGACY_STORAGE_KEY_V3, LEGACY_STORAGE_KEYS }
