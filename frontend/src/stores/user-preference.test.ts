import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const STORAGE_KEY = 'user-preference:v1'
const LEGACY_STORAGE_KEY = 'user-preference'

describe('user-preference store', () => {
  beforeEach(() => {
    localStorage.removeItem(STORAGE_KEY)
    localStorage.removeItem(LEGACY_STORAGE_KEY)
    vi.resetModules()
  })

  afterEach(() => {
    localStorage.removeItem(STORAGE_KEY)
    localStorage.removeItem(LEGACY_STORAGE_KEY)
    vi.resetModules()
  })

  it('setDisplayCurrency 更新内存状态', async () => {
    const { useUserPreferenceStore } = await import('@/stores/user-preference')
    useUserPreferenceStore.getState().setDisplayCurrency('USD')
    expect(useUserPreferenceStore.getState().displayCurrency).toBe('USD')
  })

  it('首次 hydrate 时从旧 persist 键迁移到 v1', async () => {
    localStorage.setItem(
      LEGACY_STORAGE_KEY,
      JSON.stringify({ state: { displayCurrency: 'USD' }, version: 0 })
    )
    const { useUserPreferenceStore } = await import('@/stores/user-preference')
    await useUserPreferenceStore.persist.rehydrate()
    expect(useUserPreferenceStore.getState().displayCurrency).toBe('USD')
    expect(localStorage.getItem(LEGACY_STORAGE_KEY)).toBeNull()
    expect(localStorage.getItem(STORAGE_KEY)).not.toBeNull()
  })
})
