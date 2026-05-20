/**
 * Listing Studio Store - 草稿与最近任务持久化
 */

import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'

import type { ListingStudioInputs } from '@/types/listing-studio'

const STORAGE_KEY = 'listing-studio-storage'
const LEGACY_STORAGE_KEY = 'product-info-storage'

interface ListingStudioState {
  lastJobId: string | null
  draftInputs: ListingStudioInputs

  setLastJobId: (id: string | null) => void
  setDraftInputs: (inputs: ListingStudioInputs) => void
}

function migrateLegacyStorage(): Partial<ListingStudioState> | undefined {
  if (typeof localStorage === 'undefined') return undefined
  try {
    const raw = localStorage.getItem(LEGACY_STORAGE_KEY)
    if (!raw) return undefined
    const parsed = JSON.parse(raw) as {
      state?: { lastJobId?: string | null; draftInputs?: ListingStudioInputs }
    }
    const state = parsed.state
    if (!state) return undefined
    localStorage.removeItem(LEGACY_STORAGE_KEY)
    return {
      lastJobId: state.lastJobId ?? null,
      draftInputs: state.draftInputs ?? {},
    }
  } catch {
    return undefined
  }
}

const legacy = migrateLegacyStorage()

export const useListingStudioStore = create<ListingStudioState>()(
  persist(
    (set) => ({
      lastJobId: legacy?.lastJobId ?? null,
      draftInputs: legacy?.draftInputs ?? {},

      setLastJobId: (id) => {
        set({ lastJobId: id })
      },
      setDraftInputs: (inputs) => {
        set({ draftInputs: inputs })
      },
    }),
    {
      name: STORAGE_KEY,
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        lastJobId: state.lastJobId,
        draftInputs: state.draftInputs,
      }),
    }
  )
)

export const getLastJobId = (): string | null => useListingStudioStore.getState().lastJobId

export const setLastJobId = (id: string | null): void => {
  useListingStudioStore.getState().setLastJobId(id)
}
