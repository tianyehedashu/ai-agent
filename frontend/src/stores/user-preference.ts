/**
 * 用户展示偏好（展示货币等）
 *
 * - 组件只通过 useUserPreferenceStore 读写，禁止直接操作 localStorage
 * - 持久化由 zustand/persist + createJSONStorage 负责
 */

import { create } from 'zustand'
import { createJSONStorage, persist, type StateStorage } from 'zustand/middleware'

import type { DisplayCurrency } from '@/types/money'

const STORAGE_KEY = 'user-preference:v1'
const LEGACY_STORAGE_KEY = 'user-preference'

interface PersistedUserPreferenceV1 {
  displayCurrency: DisplayCurrency
}

interface UserPreferenceState {
  displayCurrency: DisplayCurrency
  setDisplayCurrency: (c: DisplayCurrency) => void
}

function isDisplayCurrency(value: unknown): value is DisplayCurrency {
  return value === 'USD' || value === 'CNY'
}

/** 仅 persist 层使用：读 v1 键，若无则一次性从旧 persist 键迁回 */
function createUserPreferenceStorage(): StateStorage {
  const base = localStorage
  return {
    getItem: (name: string): string | null => {
      try {
        const current = base.getItem(name)
        if (current !== null) {
          return current
        }
        const legacy = base.getItem(LEGACY_STORAGE_KEY)
        if (legacy === null) {
          return null
        }
        base.setItem(name, legacy)
        base.removeItem(LEGACY_STORAGE_KEY)
        return legacy
      } catch {
        return null
      }
    },
    setItem: (name: string, value: string): void => {
      base.setItem(name, value)
    },
    removeItem: (name: string): void => {
      base.removeItem(name)
      try {
        base.removeItem(LEGACY_STORAGE_KEY)
      } catch {
        // ignore
      }
    },
  }
}

function migratePersisted(persisted: unknown, _version: number): PersistedUserPreferenceV1 {
  if (persisted !== null && typeof persisted === 'object') {
    const row = persisted as PersistedUserPreferenceV1 & {
      state?: { displayCurrency?: unknown }
    }
    if (isDisplayCurrency(row.displayCurrency)) {
      return { displayCurrency: row.displayCurrency }
    }
    const nested = row.state?.displayCurrency
    if (isDisplayCurrency(nested)) {
      return { displayCurrency: nested }
    }
  }
  return { displayCurrency: 'CNY' }
}

export const useUserPreferenceStore = create<UserPreferenceState>()(
  persist(
    (set) => ({
      displayCurrency: 'CNY',
      setDisplayCurrency: (displayCurrency) => {
        set({ displayCurrency })
      },
    }),
    {
      name: STORAGE_KEY,
      version: 1,
      migrate: migratePersisted,
      storage: createJSONStorage(() => createUserPreferenceStorage()),
      partialize: (state): PersistedUserPreferenceV1 => ({
        displayCurrency: state.displayCurrency,
      }),
    }
  )
)
